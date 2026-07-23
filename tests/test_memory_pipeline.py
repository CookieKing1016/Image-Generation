import unittest

from agents.checklist_generator import ChecklistGenerator
from agents.memory_updater import MemoryUpdater
from agents.prompt_composer import PromptComposer
from core.schema import empty_memory


class MemoryPipelineTest(unittest.TestCase):
    def test_red_scarf_dog_memory_and_checklist(self):
        updater = MemoryUpdater()
        memory = empty_memory()

        memory = updater.update(
            memory,
            {
                "add": {
                    "main_subjects": [
                        {"name": "dog", "pose": "sitting", "position": "center"}
                    ],
                    "scene": {"background": "park"},
                },
                "update": {},
                "remove": {},
                "current_turn_goal": "generate a dog sitting in a park",
                "reason": "Initial scene setup.",
            },
            "Generate a dog sitting in a park.",
        )

        memory = updater.update(
            memory,
            {
                "add": {
                    "main_subjects": [
                        {"name": "dog", "attributes": ["wearing a red scarf"]}
                    ]
                },
                "update": {},
                "remove": {},
                "current_turn_goal": "make the dog wear a red scarf",
                "reason": "Add dog attribute.",
            },
            "Make the dog wear a red scarf.",
        )

        memory = updater.update(
            memory,
            {
                "add": {},
                "update": {"scene": {"background": "snowy forest"}},
                "remove": {},
                "current_turn_goal": "change the background to a snowy forest",
                "reason": "Replace background.",
            },
            "Change the background to a snowy forest.",
        )

        memory = updater.update(
            memory,
            {
                "add": {"constraints": ["keep the red scarf", "keep the dog pose"]},
                "update": {"scene": {"lighting": "warm lighting"}},
                "remove": {},
                "current_turn_goal": "add warm lighting",
                "reason": "Add lighting and preserve earlier requirements.",
            },
            "Add warm lighting, but keep the red scarf and dog pose.",
        )

        dog = memory["main_subjects"][0]
        self.assertEqual(dog["name"], "dog")
        self.assertEqual(dog["pose"], "sitting")
        self.assertIn("wearing a red scarf", dog["attributes"])
        self.assertEqual(memory["scene"]["background"], "snowy forest")
        self.assertEqual(memory["scene"]["lighting"], "warm lighting")
        self.assertIn("keep the red scarf", memory["constraints"])

        checklist = ChecklistGenerator().generate(memory)
        questions = "\n".join(item["question"] for item in checklist).lower()
        self.assertIn("dog as the main subject", questions)
        self.assertIn("red scarf", questions)
        self.assertIn("sitting", questions)
        self.assertIn("snowy forest", questions)
        self.assertIn("warm lighting", questions)

    def test_prompt_composer_keeps_negative_prompt_separate(self):
        memory = empty_memory()
        memory["negative_constraints"] = ["no extra animals"]
        prompt = PromptComposer().compose(memory)
        self.assertIn("no extra animals", prompt.negative)
        self.assertIn("Avoid:", prompt.generation_prompt)
        self.assertIn("Hard negative constraints", prompt.positive)

    def test_replacement_updates_supersede_conflicting_attributes_and_constraints(self):
        updater = MemoryUpdater()
        memory = empty_memory()
        memory = updater.update(
            memory,
            {
                "add": {
                    "main_subjects": [
                        {"name": "clear glass vase", "attributes": ["transparent", "clear glass"]}
                    ],
                    "constraints": ["The vase must be clear glass with no visible seams."],
                },
                "current_turn_goal": "Generate a clear glass vase.",
            },
            "Generate a clear glass vase.",
        )
        memory = updater.update(
            memory,
            {
                "update": {
                    "main_subjects": [
                        {"name": "clear glass vase", "attributes": ["white ceramic"]}
                    ]
                },
                "current_turn_goal": "Change the vase material to white ceramic instead of glass.",
            },
            "Change the vase material to white ceramic instead of glass.",
        )

        vase = memory["main_subjects"][0]
        self.assertEqual(vase["name"], "white ceramic vase")
        self.assertIn("white ceramic", vase["attributes"])
        self.assertNotIn("clear glass", " ".join(vase["attributes"]).lower())
        self.assertNotIn("clear glass", " ".join(memory["constraints"]).lower())
        self.assertIn("No transparent glass vase should be visible.", memory["negative_constraints"])

    def test_scarf_color_replacement_drops_old_color_and_adds_negative(self):
        updater = MemoryUpdater()
        memory = empty_memory()
        memory = updater.update(
            memory,
            {"add": {"main_subjects": [{"name": "fox", "attributes": ["wearing a red scarf"]}]}},
            "Make the fox wear a red scarf.",
        )
        memory = updater.update(
            memory,
            {"update": {"main_subjects": [{"name": "fox", "attributes": ["wearing a blue scarf"]}]}},
            "Change the scarf to a blue scarf, replacing the red scarf.",
        )

        attrs = memory["main_subjects"][0]["attributes"]
        self.assertIn("wearing a blue scarf", attrs)
        self.assertNotIn("wearing a red scarf", attrs)
        self.assertIn("No red scarf should be visible.", memory["negative_constraints"])

    def test_removed_object_cleans_related_constraints_and_becomes_negative(self):
        updater = MemoryUpdater()
        memory = empty_memory()
        memory = updater.update(
            memory,
            {
                "add": {
                    "main_subjects": [{"name": "black leather wallet"}],
                    "objects": [{"name": "credit card"}],
                    "constraints": [
                        "The credit card must be partially visible, extending from the wallet.",
                        "The wallet must be centered.",
                    ],
                }
            },
            "Generate a wallet with a credit card.",
        )
        memory = updater.update(
            memory,
            {"remove": {"objects": [{"name": "credit card"}]}},
            "Remove the credit card from the wallet.",
        )

        self.assertEqual(memory["objects"], [])
        self.assertIn("The wallet must be centered.", memory["constraints"])
        self.assertNotIn("credit card", " ".join(memory["constraints"]).lower())
        self.assertIn("No credit card should be visible.", memory["negative_constraints"])
        self.assertIn("No card-like rectangle should protrude from the wallet.", memory["negative_constraints"])
        self.assertIn("clean closed edges", " ".join(memory["constraints"]).lower())

    def test_no_readable_text_removes_visible_writing_constraint(self):
        updater = MemoryUpdater()
        memory = empty_memory()
        memory = updater.update(
            memory,
            {
                "add": {
                    "objects": [{"name": "classroom blackboard", "attributes": ["large", "with chalk writing"]}],
                    "constraints": ["The blackboard should show visible chalk writing."],
                }
            },
            "Generate a classroom blackboard.",
        )
        memory = updater.update(
            memory,
            {
                "add": {"negative_constraints": ["No readable text on the blackboard"]},
                "current_turn_goal": "Do not include readable text on the blackboard.",
            },
            "Do not include readable text on the blackboard.",
        )

        constraints = " ".join(memory["constraints"]).lower()
        attrs = " ".join(memory["objects"][0]["attributes"]).lower()
        self.assertNotIn("chalk writing", attrs)
        self.assertNotIn("visible chalk writing", constraints)
        self.assertIn("non-readable chalk smudges", constraints)
        self.assertIn("No readable text on the blackboard.", memory["negative_constraints"])

    def test_same_name_counted_objects_keep_distinct_instances(self):
        updater = MemoryUpdater()
        memory = empty_memory()
        memory = updater.update(
            memory,
            {
                "add": {
                    "objects": [
                        {"name": "flower", "attributes": ["petal", "stem"], "position": "left"},
                        {"name": "flower", "attributes": ["petal", "stem"], "position": "center"},
                        {"name": "flower", "attributes": ["petal", "stem"], "position": "right"},
                    ],
                    "constraints": ["There must be exactly three flowers in the vase."],
                }
            },
            "Generate exactly three flowers.",
        )
        self.assertEqual(len(memory["objects"]), 3)

        memory = updater.update(
            memory,
            {"update": {"objects": [{"name": "flower", "attributes": ["purple petal"]}]}},
            "Make the flowers purple.",
        )
        self.assertEqual(len(memory["objects"]), 3)
        for flower in memory["objects"]:
            self.assertIn("purple petal", flower["attributes"])
        self.assertIn("Show exactly three fully bloomed flowers inside the vase.", memory["constraints"])
        self.assertIn("Do not show fewer or more than three flowers.", memory["negative_constraints"])


if __name__ == "__main__":
    unittest.main()
