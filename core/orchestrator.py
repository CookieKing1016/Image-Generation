"""Single-turn orchestration for the first-stage demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any, Dict, List

from agents.checklist_generator import ChecklistGenerator
from agents.clarifier import Clarifier
from agents.evaluator import ChecklistEvaluator
from agents.intent_parser import IntentParser
from agents.memory_updater import MemoryUpdater
from agents.prompt_composer import PromptBundle, PromptComposer
from agents.execution_router import ExecutionRouter
from agents.mask_planner import MaskPlanner
from agents.region_locator import RegionLocator
from agents.task_planner import TaskPlanner
from core.blackboard import Blackboard
from core.evaluation_dispatcher import EvaluationDispatcher
from core.image_metrics import compare_images
from core.run_logger import RunLogger, summarize_api_response
from core.schema import empty_memory, normalize_memory
from core.task_graph import TaskGraph
from tools.config import Settings
from tools.aimlapi_client import AIMLAPIClient
from tools.image_editor import SiliconFlowImageEditor
from tools.segmenter import create_segmenter
from tools.siliconflow_client import SiliconFlowClient, first_image_url


@dataclass
class TurnResult:
    turn_index: int
    instruction: str
    delta: Dict[str, Any]
    memory: Dict[str, Any]
    prompt: PromptBundle
    checklist: List[Dict[str, Any]]
    evaluation: Dict[str, Any]
    image_path: Path
    run_dir: Path
    task_plan: TaskGraph
    execution: Dict[str, Any]


class Mem2ImageOrchestrator:
    def __init__(self, settings: Settings, run_id: str = ""):
        self.client = SiliconFlowClient(settings)
        self.aimlapi_client = AIMLAPIClient(settings)
        self.intent_parser = IntentParser(self.client)
        self.memory_updater = MemoryUpdater()
        self.prompt_composer = PromptComposer()
        self.task_planner = TaskPlanner()
        self.execution_router = ExecutionRouter()
        self.image_editor = SiliconFlowImageEditor(self.client, self.aimlapi_client)
        self.region_locator = RegionLocator(self.client)
        self.mask_planner = MaskPlanner(self.region_locator, create_segmenter(settings))
        self.checklist_generator = ChecklistGenerator()
        self.clarifier = Clarifier()
        self.evaluator = ChecklistEvaluator(
            self.client,
            max_retries=settings.vlm_max_retries,
            retry_delay_seconds=settings.vlm_retry_delay_seconds,
        )
        self.evaluation_dispatcher = EvaluationDispatcher()
        self.logger = RunLogger(run_id or None)

    @property
    def run_id(self) -> str:
        return self.logger.run_id

    @property
    def run_dir(self) -> Path:
        return self.logger.run_dir

    def run_turn(
        self,
        instruction: str,
        memory: Dict[str, Any] = None,
        turn_index: int = 1,
        previous_image: Path | None = None,
    ) -> TurnResult:
        current_memory = normalize_memory(memory or empty_memory())
        turn_dir = self.logger.turn_dir(turn_index)
        api_summary: Dict[str, Any] = {}
        blackboard = Blackboard()
        mask_plan = None
        editor_backend = ""

        try:
            delta = self.intent_parser.parse(instruction, current_memory)
            blackboard.record("intent_parser", "parsed_delta", {"delta": delta})
        except Exception as exc:
            self.logger.save_error(turn_index, "intent_parser", exc)
            raise RuntimeError(f"[intent_parser] {exc}") from exc

        updated_memory = self.memory_updater.update(current_memory, delta, instruction)
        prompt = self.prompt_composer.compose(updated_memory)
        task_plan = self.task_planner.plan(
            delta=delta,
            memory=updated_memory,
            instruction=instruction,
            has_previous_image=bool(previous_image and previous_image.is_file()),
        )
        blackboard.record("task_planner", "planned_tasks", {"tasks": task_plan.to_list()})
        mask_path = None
        if previous_image and previous_image.is_file():
            try:
                mask_plan = self.mask_planner.plan(previous_image, task_plan, updated_memory, turn_dir)
                mask_path = mask_plan.mask_path
                blackboard.record("mask_planner", "planned_mask", mask_plan.to_dict())
            except Exception as exc:
                blackboard.record(
                    "mask_planner",
                    "mask_fallback",
                    {"error_type": type(exc).__name__, "message": str(exc)},
                )
        execution = self.execution_router.decide(task_plan, previous_image, self.image_editor.available, mask_path=mask_path)
        blackboard.record("execution_router", "route_selected", execution.to_dict())

        image_path = turn_dir / "image.png"
        if execution.mode == "blocked_edit" and previous_image is not None:
            shutil.copy2(previous_image, image_path)
            blackboard.record(
                "image_editor",
                "edit_blocked",
                {"reason": execution.reason, "preserved_image": str(previous_image)},
            )
        if execution.mode in {"masked_edit", "reference_edit"} and previous_image is not None:
            try:
                edit_instruction = _build_edit_instruction(instruction, task_plan)
                edit_result = self.image_editor.edit(
                    image_path=previous_image,
                    instruction=edit_instruction,
                    destination=image_path,
                    negative_prompt=prompt.negative,
                    mask_path=mask_path,
                )
                api_summary["image_edit"] = summarize_api_response(edit_result.response)
                blackboard.record(
                    "image_editor",
                    "edited_image",
                    {
                        "mode": execution.mode,
                        "image_path": str(image_path),
                        "candidate_path": str(edit_result.candidate_path or ""),
                        "model": self.client.settings.image_edit_model,
                        "backend": edit_result.backend,
                    },
                )
                editor_backend = edit_result.backend
            except Exception as exc:
                execution = self.execution_router.decide(task_plan, previous_image, editor_available=False, mask_path=mask_path)
                blackboard.record(
                    "image_editor",
                    "edit_fallback",
                    {"error_type": type(exc).__name__, "message": str(exc), "fallback_mode": execution.mode},
                )

        if execution.mode not in {"masked_edit", "reference_edit", "blocked_edit"}:
            try:
                image_response, generation_model, generation_failures = self.client.generate_image_with_fallback(prompt.generation_prompt)
                api_summary["image_generation"] = {
                    **summarize_api_response(image_response),
                    "selected_model": generation_model,
                    "failed_model_attempts": generation_failures,
                }
                image_url = first_image_url(image_response)
                self.client.download_file(image_url, image_path)
                blackboard.record(
                    "generator",
                    "generated_image",
                    {
                        "mode": execution.mode,
                        "image_path": str(image_path),
                        "model": generation_model,
                        "failed_model_attempts": generation_failures,
                    },
                )
            except Exception as exc:
                self.logger.save_error(turn_index, "image_generation", exc)
                raise RuntimeError(f"[image_generation] {exc}") from exc

        is_benchmark = self.client.settings.evaluation_mode == "benchmark"
        is_interactive_edit = self.client.settings.evaluation_mode == "interactive" and previous_image is not None
        checklist = self.checklist_generator.generate(updated_memory) if (is_benchmark or is_interactive_edit) else []
        has_residual_risk = any(
            item.get("drift_type") == "old_attribute_residual"
            for item in checklist
        )
        should_sync_evaluate = is_benchmark or (
            is_interactive_edit
            and has_residual_risk
            and self.client.settings.residual_auto_retry
        )
        should_async_evaluate = is_interactive_edit and not should_sync_evaluate
        if should_sync_evaluate:
            try:
                evaluation = self.evaluator.evaluate(
                    image_path=image_path,
                    checklist=checklist,
                    memory=updated_memory,
                    prompt=prompt.positive,
                )
                evaluation["status"] = "completed"
                blackboard.record(
                    "evaluator",
                    "checklist_evaluated",
                    {"checklist_score": evaluation.get("checklist_score"), "failed_items": evaluation.get("failed_items", [])},
                )
            except Exception as exc:
                self.logger.save_error(turn_index, "vlm_evaluator", exc)
                raise RuntimeError(f"[vlm_evaluator] {exc}") from exc
        elif should_async_evaluate:
            evaluation = {
                "status": "pending",
                "summary": "Interactive edit evaluation is running in the background.",
                "items": [],
                "failed_items": [],
            }
            blackboard.record("evaluation_dispatcher", "scheduled", {"mode": "async_edit"})
        else:
            evaluation = {
                "status": "skipped",
                "summary": "Interactive first-turn generation skips VLM evaluation.",
                "items": [],
                "failed_items": [],
            }
            blackboard.record("evaluator", "skipped", {"mode": self.client.settings.evaluation_mode})

        refinement_attempts = [
            {
                "attempt_index": 0,
                "status": "completed",
                "instruction": instruction,
                "score": evaluation.get("checklist_score"),
                "metadata": {"candidate_path": str(image_path)},
            }
        ]
        refinement_artifacts: List[Dict[str, Any]] = []
        if should_sync_evaluate:
            image_path, evaluation, refinement_attempts, refinement_artifacts = self._run_refinements(
                image_path=image_path,
                instruction=instruction,
                prompt=prompt,
                checklist=checklist,
                memory=updated_memory,
                task_plan=task_plan,
                mask_path=mask_path,
                initial_evaluation=evaluation,
                attempts=refinement_attempts,
                blackboard=blackboard,
            )

        image_comparison = compare_images(previous_image, image_path, mask_path) if previous_image and previous_image.is_file() else {}
        evaluation_dimensions = {"checklist_score": evaluation.get("checklist_score")}
        if image_comparison.get("available"):
            evaluation_dimensions["global_pixel_similarity_proxy"] = image_comparison.get("global_pixel_similarity")
        if image_comparison.get("edit_locality_available"):
            evaluation_dimensions["edit_locality"] = image_comparison.get("edit_locality")
        execution_data = execution.to_dict()
        execution_data["editor_backend"] = editor_backend
        execution_data["image_comparison"] = image_comparison

        self.logger.save_turn_artifacts(
            turn_index=turn_index,
            instruction=instruction,
            delta=delta,
            memory=updated_memory,
            prompt_positive=prompt.positive,
            prompt_negative=prompt.negative,
            checklist=checklist,
            evaluation=evaluation,
            image_path=image_path,
            api_summary=api_summary,
            task_plan=task_plan.to_list(),
            agent_events=blackboard.to_list(),
            image_artifacts=[
                {"artifact_type": "previous_image", "path": str(previous_image or ""), "metadata": {}},
                {"artifact_type": "mask", "path": str(mask_path or ""), "metadata": {"source": "mask_planner"}},
                *[
                    {
                        "artifact_type": f"task_mask_{item.get('task_id', 'unknown')}",
                        "path": item.get("path", ""),
                        "metadata": {key: value for key, value in item.items() if key != "path"},
                    }
                    for item in (mask_plan.task_masks if mask_plan else [])
                ],
                {"artifact_type": "final_image", "path": str(image_path), "metadata": {"execution_mode": execution.mode, "image_comparison": image_comparison}},
                *refinement_artifacts,
            ],
            refinement_attempts=[{**attempt, "metadata": {**attempt.get("metadata", {}), "execution": execution_data}} for attempt in refinement_attempts],
            evaluation_dimensions=evaluation_dimensions,
        )
        if should_async_evaluate:
            self.evaluation_dispatcher.submit(
                evaluator=self.evaluator,
                image_path=image_path,
                checklist=checklist,
                memory=updated_memory,
                prompt=prompt.positive,
                on_success=lambda completed: self.logger.save_async_evaluation(
                    turn_index,
                    checklist,
                    {**completed, "status": "completed"},
                ),
                on_error=lambda error: self.logger.save_error(turn_index, "async_vlm_evaluator", error),
            )

        return TurnResult(
            turn_index=turn_index,
            instruction=instruction,
            delta=delta,
            memory=updated_memory,
            prompt=prompt,
            checklist=checklist,
            evaluation=evaluation,
            image_path=image_path,
            run_dir=self.logger.run_dir,
            task_plan=task_plan,
            execution=execution_data,
        )

    def _run_refinements(
        self,
        image_path: Path,
        instruction: str,
        prompt: PromptBundle,
        checklist: List[Dict[str, Any]],
        memory: Dict[str, Any],
        task_plan: TaskGraph,
        mask_path: Path | None,
        initial_evaluation: Dict[str, Any],
        attempts: List[Dict[str, Any]],
        blackboard: Blackboard,
    ) -> tuple[Path, Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        best_path = image_path
        best_evaluation = initial_evaluation
        best_evaluation["status"] = "completed"
        artifacts: List[Dict[str, Any]] = []
        for attempt_index in range(1, max(0, self.client.settings.refinement_max_attempts) + 1):
            if not self.clarifier.should_refine(best_evaluation, self.client.settings.refinement_score_threshold):
                break
            if not self.image_editor.available or not mask_path:
                attempts.append({"attempt_index": attempt_index, "status": "skipped", "instruction": "", "score": best_evaluation.get("checklist_score"), "metadata": {"reason": "image editor or reliable mask is unavailable"}})
                break
            repair_instruction = self.clarifier.build_instruction(instruction, best_evaluation, task_plan)
            candidate_path = best_path.parent / f"refinement_{attempt_index:02d}.png"
            try:
                self.image_editor.edit(best_path, repair_instruction, candidate_path, prompt.negative, mask_path)
                candidate_evaluation = self.evaluator.evaluate(candidate_path, checklist, memory, prompt.positive)
                candidate_evaluation["status"] = "completed"
                candidate_score = float(candidate_evaluation.get("checklist_score", 0.0))
                previous_critical_failures = _critical_failure_count(best_evaluation)
                candidate_critical_failures = _critical_failure_count(candidate_evaluation)
                accepted = (
                    candidate_critical_failures < previous_critical_failures
                    or (
                        candidate_critical_failures == previous_critical_failures
                        and candidate_score > float(best_evaluation.get("checklist_score", 0.0))
                    )
                )
                attempts.append(
                    {
                        "attempt_index": attempt_index,
                        "status": "accepted" if accepted else "rejected",
                        "failure_reason": ",".join(candidate_evaluation.get("drift_types", [])),
                        "instruction": repair_instruction,
                        "score": candidate_score,
                        "metadata": {
                            "candidate_path": str(candidate_path),
                            "critical_failures_before": previous_critical_failures,
                            "critical_failures_after": candidate_critical_failures,
                        },
                    }
                )
                artifacts.append({"artifact_type": "refinement_candidate", "path": str(candidate_path), "metadata": {"attempt_index": attempt_index, "accepted": accepted, "checklist_score": candidate_score}})
                blackboard.record("clarifier", "refinement_evaluated", {"attempt_index": attempt_index, "accepted": accepted, "checklist_score": candidate_score})
                if accepted:
                    best_path, best_evaluation = candidate_path, candidate_evaluation
            except Exception as exc:
                attempts.append({"attempt_index": attempt_index, "status": "failed", "instruction": repair_instruction, "score": None, "metadata": {"error_type": type(exc).__name__, "message": str(exc)}})
                blackboard.record("clarifier", "refinement_failed", {"attempt_index": attempt_index, "error_type": type(exc).__name__, "message": str(exc)})
                break
        return best_path, best_evaluation, attempts, artifacts


MemoryTalk2ImageOrchestrator = Mem2ImageOrchestrator


def _build_edit_instruction(instruction: str, task_plan: TaskGraph) -> str:
    operations = "; ".join(
        f"{task.operation} target={task.target} region={task.affected_region}"
        for task in task_plan.tasks
    )
    preserve = []
    for task in task_plan.tasks:
        preserve.extend(task.preserve)
    preserve_text = ", ".join(dict.fromkeys(item for item in preserve if item)) or "all unmentioned visual details"
    has_subject_replacement = any(task.operation == "replace_object" for task in task_plan.tasks)
    replacement_guidance = ""
    if has_subject_replacement:
        replacement_guidance = (
            " This is a whole-subject appearance replacement. Preserve the target's pose, position, scale, "
            "camera framing, scene lighting, and contact shadow, while replacing only the requested identity or breed."
        )
    has_masked_local_edit = any(task.requires_mask and task.operation != "replace_object" for task in task_plan.tasks)
    boundary_guidance = ""
    if has_masked_local_edit:
        boundary_guidance = (
            " Match the surrounding lighting, texture, perspective, and contact shadows at the edited boundary. "
            "Do not create a cutout edge, halo, or rectangular patch."
        )
    return (
        "Edit the provided source image. Apply only this user request: "
        f"{instruction}. Planned operation: {operations}. "
        f"Preserve {preserve_text}. Do not redesign the full scene or change unrelated regions."
        f"{replacement_guidance}"
        f"{boundary_guidance}"
    )


def _critical_failure_count(evaluation: Dict[str, Any]) -> int:
    return sum(
        1
        for item in evaluation.get("items", [])
        if item.get("critical") and not item.get("passed")
    )
