"""Translate memory deltas into an explicit, executable editing task graph."""

from __future__ import annotations

from typing import Any, Dict, List

from core.schema import ensure_list, normalize_delta
from core.task_graph import EditTask, TaskGraph


class TaskPlanner:
    def plan(
        self,
        delta: Dict[str, Any],
        memory: Dict[str, Any],
        instruction: str,
        has_previous_image: bool,
    ) -> TaskGraph:
        normalized = normalize_delta(delta)
        if not has_previous_image:
            return TaskGraph([EditTask("task_01", "generate", instruction=instruction)])

        tasks: List[EditTask] = []
        preserve = _preserve_targets(memory)
        structured_updates = [
            item
            for section in ("main_subjects", "objects")
            for item in ensure_list(normalized["update"].get(section))
            if isinstance(item, dict) and (item.get("attribute_slots") or item.get("attribute_states"))
        ]
        for section_name in ("main_subjects", "objects"):
            for item in ensure_list(normalized["remove"].get(section_name)):
                if structured_updates and _looks_like_attribute_target(item):
                    continue
                tasks.append(self._task("remove_object", item, instruction, preserve, memory, requires_mask=True))
            for item in ensure_list(normalized["update"].get(section_name)):
                operation = _update_operation(item)
                tasks.append(self._task(operation, item, instruction, preserve, memory, requires_mask=True))
            for item in ensure_list(normalized["add"].get(section_name)):
                if structured_updates and _looks_like_attribute_target(item):
                    continue
                tasks.append(self._task("add_object", item, instruction, preserve, memory, requires_mask=True))

        if normalized["update"].get("scene") or normalized["update"].get("style"):
            tasks.append(
                EditTask(
                    task_id="",
                    operation="change_background_or_style",
                    target="scene_or_style",
                    instruction=instruction,
                    affected_region="background",
                    preserve=preserve,
                    requires_mask=True,
                )
            )

        if not tasks:
            tasks.append(EditTask("", "change_attribute", instruction=instruction, preserve=preserve, requires_mask=True))

        previous_id = ""
        for index, task in enumerate(tasks, 1):
            task.task_id = f"task_{index:02d}"
            task.depends_on = [previous_id] if previous_id else []
            previous_id = task.task_id
        return TaskGraph(tasks)

    @staticmethod
    def _task(
        operation: str,
        item: Any,
        instruction: str,
        preserve: List[str],
        memory: Dict[str, Any],
        requires_mask: bool,
    ) -> EditTask:
        if isinstance(item, dict):
            target = _resolve_entity_id(item, memory)
            region = _affected_region(item, operation, target)
            metadata = {"position": str(item.get("position", "")), "raw_item": item}
        else:
            target = str(item)
            region = target
            metadata = {}
        return EditTask(
            task_id="",
            operation=operation,
            target=target,
            instruction=instruction,
            affected_region=region,
            preserve=preserve,
            requires_mask=requires_mask,
            metadata=metadata,
        )


def _preserve_targets(memory: Dict[str, Any]) -> List[str]:
    targets: List[str] = []
    for collection in ("main_subjects", "objects"):
        for item in memory.get(collection, []):
            if not isinstance(item, dict) or item.get("status", "active") != "active":
                continue
            name = str(item.get("entity_id") or item.get("name") or "").strip()
            if name:
                targets.append(name)
            targets.extend(str(value) for value in ensure_list(item.get("preserve")) if str(value).strip())
    return list(dict.fromkeys(targets))


def _update_operation(item: Any) -> str:
    """Route whole-subject identity changes away from rectangle-mask compositing.

    Intent extraction commonly repeats an unchanged position with every entity
    update. A truthy ``position`` therefore cannot alone mean that the user
    wants to move the entity. Breed/identity changes need a reference edit so
    the editor can rebuild silhouette, hair, contact shadow, and expression.
    """
    if not isinstance(item, dict):
        return "change_attribute"
    attributes = _attribute_text(item)
    if item.get("attribute_slots") or item.get("attribute_states"):
        return "change_attribute"
    if any(marker in attributes for marker in ("breed:", "identity:", "species:", "品种", "物种", "角色替换")):
        return "replace_object"
    if item.get("position") and not item.get("attributes"):
        return "move_object"
    return "change_attribute"


def _affected_region(item: Dict[str, Any], operation: str, target: str) -> str:
    if operation != "change_attribute":
        return str(item.get("name") or target)
    attributes = _attribute_text(item)
    regions = (
        ("ribbon", ("ribbon", "bow", "缎带", "丝带", "蝴蝶结")),
        ("scarf", ("scarf", "围巾")),
        ("collar", ("collar", "项圈")),
        ("hat", ("hat", "帽")),
        ("shirt", ("shirt", "jacket", "dress", "clothes", "衣服", "外套")),
        ("eyes", ("eye", "眼睛")),
        ("hair", ("hair", "发型", "头发")),
    )
    for region, markers in regions:
        if any(marker in attributes for marker in markers):
            return region
    return str(item.get("name") or target)


def _attribute_text(item: Dict[str, Any]) -> str:
    parts = [str(value) for value in ensure_list(item.get("attributes"))]
    for key in ("attribute_slots", "attribute_states"):
        value = item.get(key)
        if isinstance(value, dict):
            parts.extend(str(key) for key in value)
            parts.extend(str(value) for value in value.values())
    return " ".join(parts).lower()


def _looks_like_attribute_target(item: Any) -> bool:
    text = str(item.get("name", "") if isinstance(item, dict) else item).lower()
    return any(marker in text for marker in ("ribbon", "bow", "缎带", "丝带", "蝴蝶结", "scarf", "围巾", "collar", "项圈"))


def _resolve_entity_id(item: Dict[str, Any], memory: Dict[str, Any]) -> str:
    explicit = str(item.get("entity_id", "")).strip()
    if explicit:
        return explicit
    name = str(item.get("name", "")).strip()
    lowered = name.lower()
    for collection in ("main_subjects", "objects"):
        for entity in memory.get(collection, []):
            if not isinstance(entity, dict):
                continue
            entity_name = str(entity.get("name", "")).strip().lower()
            if entity_name == lowered or (lowered and (lowered in entity_name or entity_name in lowered)):
                return str(entity.get("entity_id") or name or "visual_entity")
    return name or "visual_entity"
