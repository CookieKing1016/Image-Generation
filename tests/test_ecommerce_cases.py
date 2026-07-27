import unittest
from pathlib import Path

from agents.checklist_generator import ChecklistGenerator
from core.schema import normalize_memory
from scripts.run_benchmark import load_benchmark


class EcommerceCaseTest(unittest.TestCase):
    def test_ecommerce_cases_are_valid_and_mask_focused(self):
        path = Path(__file__).resolve().parents[1] / "data" / "ecommerce_mask_cases.json"
        benchmark = load_benchmark(path)
        self.assertEqual(benchmark["name"], "ecommerce_product_marketing_mask_v1")
        self.assertEqual(len(benchmark["cases"]), 3)
        for case in benchmark["cases"]:
            self.assertEqual(len(case["turns"]), 4)
            self.assertTrue(case["evaluation_focus"])
            self.assertTrue(
                any(
                    marker in focus
                    for focus in case["evaluation_focus"]
                    for marker in ("retention", "locality", "boundary", "product")
                )
            )

    def test_chinese_checklist_ids_are_unique_for_sqlite(self):
        checklist = ChecklistGenerator().generate(
            normalize_memory(
                {
                    "main_subjects": [
                        {
                            "name": "护肤精华瓶",
                            "attributes": ["瓶身透明", "液体呈淡金色", "瓶颈处系有黑色缎带"],
                            "pose": "直立",
                            "position": "中心",
                        }
                    ],
                    "objects": [{"name": "白色台座"}, {"name": "小白花"}],
                }
            )
        )
        ids = [item["id"] for item in checklist]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any("subject_" in item_id and len(item_id) > len("subject_") for item_id in ids))


if __name__ == "__main__":
    unittest.main()
