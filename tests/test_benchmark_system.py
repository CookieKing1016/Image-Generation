import tempfile
import unittest
from pathlib import Path

from core import database
from core.metrics import summarize_methods
from methods import create_method
from scripts.run_benchmark import BENCHMARK_PATH, load_benchmark


class BenchmarkSystemTest(unittest.TestCase):
    def test_benchmark_has_ten_four_turn_cases(self):
        benchmark = load_benchmark(BENCHMARK_PATH)
        self.assertEqual(len(benchmark["cases"]), 10)
        for case in benchmark["cases"]:
            self.assertEqual(len(case["turns"]), 4)
            for turn in case["turns"]:
                self.assertGreater(len(turn["checklist"]), 0)

    def test_current_only_and_full_history_prompts_differ(self):
        current_only = create_method("current-only")
        full_history = create_method("full-history")
        history = ["Generate a dog sitting in a park."]
        instruction = "Make the dog wear a red scarf."

        current_prompt = current_only.build_turn(instruction, history).positive_prompt
        full_prompt = full_history.build_turn(instruction, history).positive_prompt

        self.assertIn(instruction, current_prompt)
        self.assertNotIn(history[0], current_prompt)
        self.assertIn(history[0], full_prompt)
        self.assertIn(instruction, full_prompt)

    def test_method_summary_metrics_from_checklist_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "metrics.sqlite3"
            run_dir = Path(temp_dir) / "run"

            database.save_turn(
                run_id="bench__current-only__case_a",
                run_dir=run_dir,
                turn_index=1,
                instruction="Turn instruction",
                delta={},
                memory={},
                prompt_positive="prompt",
                prompt_negative="negative",
                checklist=[
                    {
                        "id": "history_item",
                        "question": "History item?",
                        "target": "yes",
                        "type": "attribute",
                        "source": "history",
                        "critical": True,
                        "drift_type": "attribute_drift",
                    },
                    {
                        "id": "current_item",
                        "question": "Current item?",
                        "target": "yes",
                        "type": "scene",
                        "source": "current",
                        "critical": False,
                        "drift_type": "scene_drift",
                    },
                    {
                        "id": "current_item_2",
                        "question": "Second current item?",
                        "target": "yes",
                        "type": "current_turn",
                        "source": "",
                        "critical": False,
                        "drift_type": "current_turn_failure",
                    },
                ],
                evaluation={
                    "items": [
                        {"id": "history_item", "answer": "yes", "passed": True},
                        {"id": "current_item", "answer": "yes", "passed": True},
                        {"id": "current_item_2", "answer": "no", "passed": False},
                    ],
                    "checklist_score": 0.6667,
                    "failed_items": ["Current item failed"],
                },
                image_path=run_dir / "image.png",
                api_summary={},
                db_path=db_path,
                method="current-only",
                case_id="case_a",
                metadata={"benchmark_run_id": "bench"},
            )

            summary = summarize_methods(db_path, benchmark_run_id="bench")
            self.assertEqual(len(summary), 1)
            self.assertEqual(summary[0]["method"], "current-only")
            self.assertEqual(summary[0]["avg_checklist_score"], 0.6667)
            self.assertEqual(summary[0]["history_retention_rate"], 1.0)
            self.assertEqual(summary[0]["current_turn_success_rate"], 0.0)
            self.assertEqual(summary[0]["drift_count"], 1)


if __name__ == "__main__":
    unittest.main()
