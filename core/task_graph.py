"""Small, serializable task graph for multi-turn image editing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List


VALID_OPERATIONS = {
    "generate",
    "add_object",
    "remove_object",
    "replace_object",
    "change_attribute",
    "move_object",
    "change_background_or_style",
}


@dataclass
class EditTask:
    task_id: str
    operation: str
    target: str = ""
    instruction: str = ""
    affected_region: str = ""
    preserve: List[str] = field(default_factory=list)
    requires_mask: bool = False
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskGraph:
    def __init__(self, tasks: Iterable[EditTask] = ()):
        self.tasks = list(tasks)
        self.validate()

    def validate(self) -> None:
        seen = set()
        for task in self.tasks:
            if task.operation not in VALID_OPERATIONS:
                raise ValueError(f"Unsupported image edit operation: {task.operation}")
            if task.task_id in seen:
                raise ValueError(f"Duplicate task id: {task.task_id}")
            if any(dep not in seen for dep in task.depends_on):
                raise ValueError("Task dependencies must refer to earlier tasks.")
            seen.add(task.task_id)

    def to_list(self) -> List[Dict[str, Any]]:
        return [task.to_dict() for task in self.tasks]
