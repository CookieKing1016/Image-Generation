"""VLM checklist evaluator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.schema import extract_json_object, json_dumps
from tools.siliconflow_client import SiliconFlowClient, first_message_text


EVALUATOR_PROMPT = """You are the VLM Evaluator for Mem2Image.
Inspect the provided image and answer each checklist item. Return strict JSON:
{
  "items": [
    {
      "id": "same id from checklist",
      "answer": "yes or no",
      "target": "yes or no",
      "passed": true,
      "confidence": 0.0,
      "reason": "short visual evidence"
    }
  ],
  "checklist_score": 0.0,
  "failed_items": ["short failure descriptions"],
  "summary": "one sentence"
}

Rules:
- Answer only from visible image evidence.
- For each item, passed is true only when answer matches target.
- checklist_score is passed item count divided by total item count.
- Include drift_type/source/critical metadata from checklist when available.
- Do not include commentary outside JSON.
"""


class ChecklistEvaluator:
    def __init__(self, client: SiliconFlowClient):
        self.client = client

    def evaluate(
        self,
        image_path: Path,
        checklist: List[Dict[str, Any]],
        memory: Dict[str, Any],
        prompt: str,
    ) -> Dict[str, Any]:
        request_prompt = (
            f"{EVALUATOR_PROMPT}\n\n"
            "Generation prompt:\n"
            f"{prompt}\n\n"
            "Visual Intent Memory:\n"
            f"{json_dumps(memory)}\n\n"
            "Checklist:\n"
            f"{json_dumps(checklist)}"
        )
        response = self.client.vision_completion(request_prompt, image_path)
        parsed = extract_json_object(first_message_text(response))
        return normalize_evaluation(parsed, checklist)


def normalize_evaluation(raw: Dict[str, Any], checklist: List[Dict[str, Any]]) -> Dict[str, Any]:
    expected_by_id = {item["id"]: item for item in checklist}
    items = []
    for raw_item in raw.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        item_id = str(raw_item.get("id", ""))
        expected = expected_by_id.get(item_id, {})
        target = str(raw_item.get("target") or expected.get("target", "yes")).lower()
        answer = _normalize_answer(raw_item.get("answer"))
        # Treat the yes/no answer as the source of truth. VLMs sometimes return
        # a stale or contradictory `passed` boolean while the answer is valid.
        passed = answer == target
        if answer == "unknown":
            passed = False
        items.append(
            {
                "id": item_id,
                "question": expected.get("question", raw_item.get("question", "")),
                "target": target,
                "answer": answer,
                "passed": passed,
                "confidence": _float_or_zero(raw_item.get("confidence")),
                "reason": str(raw_item.get("reason", "")),
                "type": expected.get("type", raw_item.get("type", "")),
                "source": expected.get("source", raw_item.get("source", "")),
                "critical": bool(expected.get("critical", raw_item.get("critical", False))),
                "drift_type": expected.get("drift_type", raw_item.get("drift_type", "")),
            }
        )

    answered_ids = {item["id"] for item in items}
    for expected in checklist:
        if expected["id"] not in answered_ids:
            items.append(
                {
                    "id": expected["id"],
                    "question": expected["question"],
                    "target": expected["target"],
                    "answer": "unknown",
                    "passed": False,
                    "confidence": 0.0,
                    "reason": "The evaluator did not answer this item.",
                    "type": expected["type"],
                    "source": expected.get("source", ""),
                    "critical": bool(expected.get("critical", False)),
                    "drift_type": expected.get("drift_type", ""),
                }
            )

    score = 0.0
    if items:
        score = sum(1 for item in items if item["passed"]) / len(items)

    failed_items = [
        f"{item['question']} -> {item['answer']}: {item['reason']}"
        for item in items
        if not item["passed"]
    ]
    return {
        "items": items,
        "checklist_score": round(score, 4),
        "failed_items": failed_items,
        "drift_count": len(failed_items),
        "drift_types": sorted({item["drift_type"] for item in items if not item["passed"] and item.get("drift_type")}),
        "summary": str(raw.get("summary", "")),
    }


def _normalize_answer(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"yes", "no"}:
        return text
    return "unknown"


def _float_or_zero(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
