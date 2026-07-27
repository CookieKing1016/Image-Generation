"""Turn failed visual checks into a focused follow-up edit instruction."""

from __future__ import annotations

from typing import Any, Dict

from core.task_graph import TaskGraph


class Clarifier:
    """Deterministic repair planner driven by evaluator evidence.

    It deliberately does not make another LLM call: a failed VLM checklist
    already contains the grounded question and visual reason needed to ask the
    image editor for a narrower repair. This makes retry cost predictable and
    keeps the source of a repair auditable in the experiment log.
    """

    def should_refine(self, evaluation: Dict[str, Any], threshold: float) -> bool:
        if not evaluation.get("items"):
            return False
        if any(item.get("critical") and not item.get("passed") for item in evaluation["items"]):
            return True
        return float(evaluation.get("checklist_score", 0.0)) < threshold

    def build_instruction(
        self,
        original_instruction: str,
        evaluation: Dict[str, Any],
        task_plan: TaskGraph,
    ) -> str:
        failed = [item for item in evaluation.get("items", []) if not item.get("passed")]
        evidence = "; ".join(
            f"Requirement: {item.get('question', '')}. Visual issue: {item.get('reason', 'not satisfied.')}"
            for item in failed[:6]
        )
        residual_guidance = ""
        if any(item.get("drift_type") == "old_attribute_residual" for item in failed):
            residual_guidance = (
                " Fully erase every remnant of the superseded attribute, including edge fragments, "
                "reflections, cast shadows, contact shadows, and color bleeding before rebuilding the replacement."
            )
        preserve = []
        for task in task_plan.tasks:
            preserve.extend(task.preserve)
        preserve_text = ", ".join(dict.fromkeys(item for item in preserve if item)) or "all unrelated subjects, pose, composition, and background"
        return (
            "Repair the supplied image only where the failed requirements require it. "
            f"Original user request: {original_instruction}. "
            f"Failed visual checks: {evidence}. "
            f"Preserve {preserve_text}. Do not introduce extra objects, undo completed edits, or redesign unmentioned regions."
            f"{residual_guidance}"
        )
