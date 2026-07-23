import tempfile
import unittest
from pathlib import Path

from core import database


class DatabaseTest(unittest.TestCase):
    def test_save_turn_persists_run_turn_and_checklist_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mem2image.sqlite3"
            run_dir = Path(temp_dir) / "runs" / "run_a"
            image_path = run_dir / "turn_01" / "image.png"

            database.save_turn(
                run_id="run_a",
                run_dir=run_dir,
                turn_index=1,
                instruction="Make a dog wear a red scarf.",
                delta={"add": {"main_subjects": [{"name": "dog"}]}},
                memory={"main_subjects": [{"name": "dog"}]},
                prompt_positive="Main subject: dog with wearing a red scarf.",
                prompt_negative="low quality",
                checklist=[
                    {
                        "id": "subject_dog_exists",
                        "question": "Is there a dog as the main subject?",
                        "target": "yes",
                        "type": "object",
                    }
                ],
                evaluation={
                    "items": [
                        {
                            "id": "subject_dog_exists",
                            "answer": "yes",
                            "passed": True,
                            "confidence": 0.9,
                            "reason": "A dog is visible.",
                        }
                    ],
                    "checklist_score": 1.0,
                    "failed_items": [],
                },
                image_path=image_path,
                api_summary={"image_generation": {"model": "test-model"}},
                db_path=db_path,
            )

            runs = database.list_runs(db_path)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], "run_a")
            self.assertEqual(runs[0]["turn_count"], 1)
            self.assertEqual(runs[0]["avg_checklist_score"], 1.0)

            turns = database.list_turns("run_a", db_path)
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["instruction"], "Make a dog wear a red scarf.")
            self.assertEqual(turns[0]["evaluation_json"]["checklist_score"], 1.0)

            with database.connect(db_path) as conn:
                item_count = conn.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0]
            self.assertEqual(item_count, 1)


if __name__ == "__main__":
    unittest.main()
