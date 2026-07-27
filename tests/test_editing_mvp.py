import unittest
import tempfile
import base64
import io
from pathlib import Path

from agents.task_planner import TaskPlanner
from agents.clarifier import Clarifier
from agents.execution_router import ExecutionRouter
from agents.mask_planner import MaskPlanner
from agents.evaluator import ChecklistEvaluator
from core.image_metrics import compare_images
from core.mask_utils import (
    composite_masked_edit,
    create_bbox_mask,
    create_position_mask,
    create_union_mask,
    invert_mask,
)
from core.schema import empty_memory, normalize_memory
from core.task_graph import EditTask, TaskGraph
from tools.config import Settings
from tools.aimlapi_client import AIMLAPIClient
from tools.image_editor import SiliconFlowImageEditor
from tools.siliconflow_client import SiliconFlowClient, SiliconFlowError


class EditingMvpTest(unittest.TestCase):
    def test_normalized_entities_receive_stable_editing_metadata(self):
        memory = normalize_memory(
            {"main_subjects": [{"name": "fox", "attributes": ["wearing a red scarf"]}]}
        )
        fox = memory["main_subjects"][0]
        self.assertEqual(fox["entity_id"], "fox_1")
        self.assertEqual(fox["entity_type"], "fox")
        self.assertEqual(fox["status"], "active")
        self.assertEqual(fox["preserve"], [])

    def test_planner_emits_masked_attribute_edit_after_first_turn(self):
        memory = normalize_memory(
            {"main_subjects": [{"name": "fox", "entity_id": "fox_1", "preserve": ["pose"]}]}
        )
        graph = TaskPlanner().plan(
            delta={"update": {"main_subjects": [{"name": "fox", "attributes": ["wearing a blue scarf"]}]}},
            memory=memory,
            instruction="Change the fox scarf to blue.",
            has_previous_image=True,
        )
        self.assertEqual(len(graph.tasks), 1)
        task = graph.tasks[0]
        self.assertEqual(task.operation, "change_attribute")
        self.assertTrue(task.requires_mask)
        self.assertIn("fox_1", task.preserve)
        self.assertEqual(task.affected_region, "scarf")

    def test_planner_targets_stable_entity_id_for_existing_object(self):
        memory = normalize_memory(
            {"objects": [{"name": "small dog", "entity_id": "dog_1"}]}
        )
        graph = TaskPlanner().plan(
            delta={"update": {"objects": [{"name": "dog", "attributes": ["blue collar"]}]}},
            memory=memory,
            instruction="Change the dog's collar to blue.",
            has_previous_image=True,
        )
        self.assertEqual(graph.tasks[0].target, "dog_1")

    def test_breed_replacement_routes_to_reference_edit_without_mask(self):
        graph = TaskPlanner().plan(
            delta={"update": {"main_subjects": [{"name": "dog", "attributes": ["breed: schnauzer"], "position": "center"}]}},
            memory=normalize_memory({"main_subjects": [{"name": "dog", "entity_id": "dog_1", "position": "center"}]}),
            instruction="Change the dog into a schnauzer, keeping the background.",
            has_previous_image=True,
        )
        self.assertEqual(graph.tasks[0].operation, "replace_object")
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            source.write_bytes(b"source")
            decision = ExecutionRouter().decide(graph, source, editor_available=True)
        self.assertEqual(decision.mode, "reference_edit")

    def test_first_turn_is_always_generation(self):
        graph = TaskPlanner().plan({}, empty_memory(), "Generate a fox.", has_previous_image=False)
        self.assertEqual(graph.tasks[0].operation, "generate")
        self.assertFalse(graph.tasks[0].requires_mask)

    def test_clarifier_uses_failed_visual_evidence_and_preserve_targets(self):
        graph = TaskPlanner().plan(
            delta={"update": {"main_subjects": [{"name": "fox", "attributes": ["blue scarf"]}]}},
            memory=normalize_memory({"main_subjects": [{"name": "fox", "entity_id": "fox_1", "preserve": ["pose"]}]}),
            instruction="Make the fox scarf blue.",
            has_previous_image=True,
        )
        evaluation = {
            "checklist_score": 0.5,
            "items": [{"passed": False, "question": "Is the fox visibly wearing a blue scarf?", "reason": "The scarf is red."}],
        }
        clarifier = Clarifier()
        self.assertTrue(clarifier.should_refine(evaluation, 0.9))
        repair = clarifier.build_instruction("Make the fox scarf blue.", evaluation, graph)
        self.assertIn("The scarf is red.", repair)
        self.assertIn("fox_1", repair)

    def test_image_edit_request_includes_source_image_without_image_size(self):
        client = SiliconFlowClient(Settings(api_key="test", image_edit_model="Qwen/Qwen-Image-Edit-2509"))
        captured = {}

        def fake_post(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"images": [{"url": "https://example.test/result.png"}]}

        client._post_json = fake_post  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            source.write_bytes(b"fake image")
            client.edit_image("Change the scarf to blue.", source, negative_prompt="no red scarf")

        self.assertEqual(captured["path"], "/images/generations")
        self.assertEqual(captured["payload"]["model"], "Qwen/Qwen-Image-Edit-2509")
        self.assertTrue(captured["payload"]["image"].startswith("data:image/png;base64,"))
        self.assertNotIn("image_size", captured["payload"])

    def test_native_inpaint_request_includes_source_and_mask(self):
        client = SiliconFlowClient(
            Settings(api_key="test", image_inpaint_model="provider/native-inpaint")
        )
        captured = {}

        def fake_post(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"images": [{"url": "https://example.test/result.png"}]}

        client._post_json = fake_post  # type: ignore[method-assign]
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            mask = Path(temp_dir) / "mask.png"
            source.write_bytes(b"source")
            mask.write_bytes(b"mask")
            client.inpaint_image("Replace the ribbon.", source, mask, negative_prompt="no black ribbon")

        self.assertEqual(captured["path"], "/images/generations")
        self.assertEqual(captured["payload"]["model"], "provider/native-inpaint")
        self.assertTrue(captured["payload"]["image"].startswith("data:image/png;base64,"))
        self.assertTrue(captured["payload"]["mask"].startswith("data:image/png;base64,"))
        self.assertEqual(captured["payload"]["negative_prompt"], "no black ribbon")

    def test_aimlapi_flux_fill_uses_binary_mask_and_openai_endpoint(self):
        client = AIMLAPIClient(
            Settings(
                aimlapi_key="test",
                image_inpaint_provider="aimlapi",
                image_inpaint_model="blackforestlabs/flux-fill",
            )
        )
        captured = {}

        def fake_post(path, payload):
            captured["path"] = path
            captured["payload"] = payload
            return {"data": [{"url": "https://example.test/result.png"}]}

        client._post_json = fake_post  # type: ignore[method-assign]
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.png"
            mask = Path(temp_dir) / "mask.png"
            Image.new("RGB", (2, 2), "white").save(source)
            soft_mask = Image.new("L", (2, 2))
            soft_mask.putdata([0, 127, 128, 255])
            soft_mask.save(mask)
            response = client.inpaint_image(
                "Replace the ribbon.",
                source,
                mask,
                negative_prompt="no black ribbon",
            )

        self.assertEqual(captured["path"], "/images/generations")
        self.assertEqual(captured["payload"]["model"], "blackforestlabs/flux-fill")
        encoded = captured["payload"]["mask"].split(",", 1)[1]
        binary = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("L")
        self.assertEqual(list(binary.get_flattened_data()), [0, 0, 255, 255])
        self.assertEqual(response["data"][0]["url"], "https://example.test/result.png")

    def test_first_image_url_accepts_openai_data_shape(self):
        from tools.siliconflow_client import first_image_url

        url = first_image_url({"data": [{"url": "https://example.test/result.png"}]})
        self.assertEqual(url, "https://example.test/result.png")

    def test_aimlapi_only_editor_is_unavailable_without_key(self):
        settings = Settings(
            image_edit_model="",
            aimlapi_key="",
            image_inpaint_provider="aimlapi",
            image_inpaint_model="blackforestlabs/flux-fill",
        )
        editor = SiliconFlowImageEditor(
            SiliconFlowClient(settings),
            AIMLAPIClient(settings),
        )
        self.assertFalse(editor.available)

    def test_clarifier_explicitly_removes_residual_edges_and_shadows(self):
        graph = TaskGraph(
            [EditTask("task_01", "change_attribute", target="bottle_1", requires_mask=True)]
        )
        evaluation = {
            "checklist_score": 0.8,
            "items": [
                {
                    "passed": False,
                    "critical": True,
                    "drift_type": "old_attribute_residual",
                    "question": "Is the old black ribbon absent?",
                    "reason": "A black edge and shadow remain.",
                }
            ],
        }
        instruction = Clarifier().build_instruction("Make the ribbon burgundy.", evaluation, graph)
        self.assertIn("edge fragments", instruction)
        self.assertIn("cast shadows", instruction)

    def test_generation_falls_back_after_model_server_error(self):
        client = SiliconFlowClient(
            Settings(
                api_key="test",
                image_model="black-forest-labs/FLUX.2-flex",
                image_fallback_models=["black-forest-labs/FLUX.1-schnell"],
            )
        )
        attempted = []

        def fake_generate(prompt, model=None):
            attempted.append(model)
            if model == "black-forest-labs/FLUX.2-flex":
                raise SiliconFlowError("SiliconFlow API failed for model 'black-forest-labs/FLUX.2-flex' at '/images/generations' with HTTP 500")
            return {"images": [{"url": "https://example.test/result.png"}]}

        client.generate_image = fake_generate  # type: ignore[method-assign]
        response, selected_model, failures = client.generate_image_with_fallback("A fox in a forest")

        self.assertEqual(response["images"][0]["url"], "https://example.test/result.png")
        self.assertEqual(selected_model, "black-forest-labs/FLUX.1-schnell")
        self.assertEqual(attempted, ["black-forest-labs/FLUX.2-flex", "black-forest-labs/FLUX.1-schnell"])
        self.assertEqual(failures[0]["model"], "black-forest-labs/FLUX.2-flex")

    def test_flux_schnell_request_omits_unsupported_tuning_fields(self):
        client = SiliconFlowClient(Settings(api_key="test"))
        captured = {}
        client._post_json = lambda path, payload: captured.update(path=path, payload=payload) or {"images": []}  # type: ignore[method-assign]

        client.generate_image("A fox", model="black-forest-labs/FLUX.1-schnell")

        self.assertNotIn("num_inference_steps", captured["payload"])
        self.assertNotIn("guidance_scale", captured["payload"])

    def test_evaluator_retries_transient_connection_close(self):
        class FlakyVisionClient:
            def __init__(self):
                self.calls = 0

            def vision_completion(self, prompt, image_path):
                self.calls += 1
                if self.calls == 1:
                    raise SiliconFlowError("SiliconFlow API connection failed: Remote end closed connection without response")
                return {
                    "choices": [
                        {
                            "message": {
                                "content": '{"items":[{"id":"fox_exists","answer":"yes","confidence":0.9,"reason":"fox visible"}],"summary":"ok"}'
                            }
                        }
                    ]
                }

        evaluator = ChecklistEvaluator(FlakyVisionClient(), max_retries=2, retry_delay_seconds=0)  # type: ignore[arg-type]
        result = evaluator.evaluate(
            image_path=Path("unused.png"),
            checklist=[{"id": "fox_exists", "question": "Is a fox visible?", "target": "yes", "type": "object"}],
            memory={},
            prompt="A fox.",
        )

        self.assertEqual(result["evaluation_attempts"], 2)
        self.assertEqual(result["checklist_score"], 1.0)

    def test_siliconflow_json_request_retries_ssl_connection_close(self):
        client = SiliconFlowClient(
            Settings(api_key="test", vlm_max_retries=2, vlm_retry_delay_seconds=0)
        )
        calls = []

        def fake_urlopen(req, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise ConnectionResetError("UNEXPECTED_EOF_WHILE_READING")

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    return b'{"ok": true}'

            return Response()

        import tools.siliconflow_client as client_module

        original_urlopen = client_module.request.urlopen
        client_module.request.urlopen = fake_urlopen
        try:
            response = client._post_json("/chat/completions", {"model": "test"})
        finally:
            client_module.request.urlopen = original_urlopen

        self.assertEqual(response, {"ok": True})
        self.assertEqual(len(calls), 2)

    def test_masked_composite_preserves_pixels_outside_edit_region(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            candidate = root / "candidate.png"
            mask = root / "mask.png"
            result = root / "result.png"
            Image.new("RGB", (100, 100), "red").save(source)
            Image.new("RGB", (100, 100), "blue").save(candidate)
            create_bbox_mask(source, (400, 400, 600, 600), mask, feather_px=0)
            composite_masked_edit(source, candidate, mask, result)
            comparison = compare_images(source, result, mask)

            with Image.open(result) as image:
                self.assertEqual(image.getpixel((10, 10)), (255, 0, 0))
                self.assertEqual(image.getpixel((50, 50)), (0, 0, 255))
            self.assertTrue(comparison["edit_locality_available"])
            self.assertGreater(comparison["edit_locality"], 0.99)

    def test_default_mask_has_soft_transition_and_context_padding(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            mask = root / "mask.png"
            Image.new("RGB", (1000, 1000), "white").save(source)
            create_bbox_mask(source, (400, 400, 600, 600), mask)
            with Image.open(mask) as image:
                self.assertEqual(image.getpixel((500, 500)), 255)
                self.assertGreater(image.getpixel((385, 500)), 0)
                self.assertLess(image.getpixel((385, 500)), 255)

    def test_background_mask_inverts_subject_protection(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            protection = root / "subjects.png"
            background = root / "background.png"
            Image.new("RGB", (100, 100), "white").save(source)
            create_union_mask(source, [(400, 400, 600, 600)], protection, feather_px=0)
            invert_mask(protection, background)
            with Image.open(background) as mask:
                self.assertEqual(mask.getpixel((50, 50)), 0)
                self.assertEqual(mask.getpixel((5, 5)), 255)

    def test_position_mask_targets_requested_side(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            mask_path = root / "left.png"
            Image.new("RGB", (100, 100), "white").save(source)
            result = create_position_mask(source, "left side", mask_path, feather_px=0)
            self.assertEqual(result, mask_path)
            with Image.open(mask_path) as mask:
                self.assertEqual(mask.getpixel((10, 50)), 255)
                self.assertEqual(mask.getpixel((90, 50)), 0)

    def test_multi_task_mask_unions_attribute_and_addition_regions(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is unavailable")

        class LocatedRibbon:
            found = True
            bbox_1000 = (400, 180, 600, 360)
            reason = "ribbon"

            def to_dict(self):
                return {"found": True, "bbox_1000": list(self.bbox_1000), "reason": self.reason}

        class FakeLocator:
            def locate(self, image_path, task):
                return LocatedRibbon()

        graph = TaskGraph(
            [
                EditTask("task_01", "change_attribute", target="bottle_1", affected_region="ribbon", requires_mask=True),
                EditTask("task_02", "add_object", target="flowers", affected_region="flowers", requires_mask=True, depends_on=["task_01"], metadata={"position": "瓶子旁边"}),
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            Image.new("RGB", (1000, 1000), "white").save(source)
            plan = MaskPlanner(FakeLocator()).plan(source, graph, {}, root)  # type: ignore[arg-type]
            self.assertEqual(len(plan.task_masks), 2)
            self.assertTrue(plan.mask_path and plan.mask_path.is_file())
            with Image.open(plan.mask_path) as mask:
                self.assertGreater(mask.getpixel((500, 250)), 0)
                self.assertGreater(mask.getpixel((200, 700)), 0)


if __name__ == "__main__":
    unittest.main()
