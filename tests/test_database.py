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
                task_plan=[
                    {
                        "task_id": "task_01",
                        "operation": "generate",
                        "target": "",
                        "affected_region": "",
                        "requires_mask": False,
                        "depends_on": [],
                    }
                ],
                agent_events=[{"agent": "planner", "event_type": "planned", "payload": {}}],
                image_artifacts=[{"artifact_type": "final_image", "path": str(image_path), "metadata": {}}],
                refinement_attempts=[{"attempt_index": 0, "status": "completed", "score": 1.0}],
                evaluation_dimensions={"checklist_score": 1.0},
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
                task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                event_count = conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0]
                artifact_count = conn.execute("SELECT COUNT(*) FROM image_artifacts").fetchone()[0]
                dimension_count = conn.execute("SELECT COUNT(*) FROM evaluation_dimensions").fetchone()[0]
            self.assertEqual(item_count, 1)
            self.assertEqual(task_count, 1)
            self.assertEqual(event_count, 1)
            self.assertEqual(artifact_count, 1)
            self.assertEqual(dimension_count, 1)

    def test_update_turn_evaluation_replaces_pending_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "mem2image.sqlite3"
            run_dir = Path(temp_dir) / "runs" / "run_async"
            checklist = [{"id": "fox_exists", "question": "Is a fox visible?", "target": "yes", "type": "object"}]
            database.save_turn(
                run_id="run_async",
                run_dir=run_dir,
                turn_index=2,
                instruction="Change the scarf.",
                delta={},
                memory={},
                prompt_positive="prompt",
                prompt_negative="",
                checklist=checklist,
                evaluation={"status": "pending", "items": [], "failed_items": []},
                image_path=run_dir / "turn_02" / "image.png",
                api_summary={},
                db_path=db_path,
            )

            database.update_turn_evaluation(
                run_id="run_async",
                turn_index=2,
                checklist=checklist,
                evaluation={
                    "status": "completed",
                    "items": [{"id": "fox_exists", "answer": "yes", "passed": True, "confidence": 0.9, "reason": "fox visible"}],
                    "checklist_score": 1.0,
                    "failed_items": [],
                },
                db_path=db_path,
            )

            turn = database.list_turns("run_async", db_path)[0]
            self.assertEqual(turn["evaluation_json"]["status"], "completed")
            self.assertEqual(turn["checklist_score"], 1.0)
            with database.connect(db_path) as conn:
                passed = conn.execute("SELECT passed FROM checklist_items WHERE run_id = 'run_async'").fetchone()[0]
            self.assertEqual(passed, 1)


if __name__ == "__main__":
    unittest.main()
