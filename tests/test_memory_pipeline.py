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


if __name__ == "__main__":
    unittest.main()

