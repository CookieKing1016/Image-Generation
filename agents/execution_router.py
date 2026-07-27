"""Choose local editing when an editor is available, otherwise log a fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.task_graph import TaskGraph


@dataclass
class ExecutionDecision:
    mode: str
    reason: str
    task_graph: TaskGraph
    mask_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "tasks": self.task_graph.to_list(),
            "mask_path": str(self.mask_path) if self.mask_path else "",
        }


class ExecutionRouter:
    def decide(
        self,
        task_graph: TaskGraph,
        previous_image: Optional[Path],
        editor_available: bool,
        mask_path: Optional[Path] = None,
    ) -> ExecutionDecision:
        if not previous_image or not previous_image.is_file():
            return ExecutionDecision("generate", "No previous image is available.", task_graph)
        if all(task.operation == "generate" for task in task_graph.tasks):
            return ExecutionDecision("generate", "Initial generation task.", task_graph)
        if editor_available and mask_path and mask_path.is_file():
            return ExecutionDecision("masked_edit", "A VLM-located mask and image editor are available.", task_graph, mask_path)
        if editor_available and all(task.operation == "replace_object" for task in task_graph.tasks):
            return ExecutionDecision("reference_edit", "Whole-subject replacement can use reference-image editing without a local mask.", task_graph)
        if editor_available:
            return ExecutionDecision("blocked_edit", "A local edit requires a reliable mask; preserved the previous image instead of regenerating the full canvas.", task_graph)
        return ExecutionDecision(
            "fallback_generate",
            "No segmentation/inpainting backend is configured; regenerated the full image and recorded the fallback.",
            task_graph,
        )
