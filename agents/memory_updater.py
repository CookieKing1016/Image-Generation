"""Deterministic Visual Intent Memory merge rules."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from core.schema import ensure_list, normalize_delta, normalize_memory


class MemoryUpdater:
    def update(self, memory: Dict[str, Any], delta: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        next_memory = normalize_memory(memory)
        normalized_delta = normalize_delta(delta)

        self._apply_section(next_memory, normalized_delta.get("add", {}), mode="add")
        self._apply_section(next_memory, normalized_delta.get("update", {}), mode="update")
        self._apply_removals(next_memory, normalized_delta.get("remove", {}))

        if normalized_delta.get("current_turn_goal"):
            next_memory["current_turn_goal"] = normalized_delta["current_turn_goal"]

        next_memory["turn_history"].append(
            {
                "turn": len(next_memory["turn_history"]) + 1,
                "instruction": instruction,
                "delta": normalized_delta,
                "current_turn_goal": next_memory["current_turn_goal"],
            }
        )
        return normalize_memory(next_memory)

    def _apply_section(self, memory: Dict[str, Any], section: Dict[str, Any], mode: str) -> None:
        if not isinstance(section, dict):
            return

        for key in ("main_subjects", "objects"):
            if key in section:
                self._merge_object_list(memory[key], ensure_list(section[key]), mode=mode)

        for key in ("scene", "style"):
            if isinstance(section.get(key), dict):
                memory[key].update(_clean_dict(section[key]))

        for key in ("constraints", "negative_constraints"):
            if key in section:
                self._extend_unique_strings(memory[key], ensure_list(section[key]))

        # Be forgiving if the LLM emits direct scene/style fields under update.
        for direct_scene_key in ("background", "lighting", "weather", "environment"):
            if direct_scene_key in section:
                memory["scene"][direct_scene_key] = section[direct_scene_key]

        for direct_style_key in ("visual_style", "color_palette", "medium"):
            if direct_style_key in section:
                memory["style"][direct_style_key] = section[direct_style_key]

    def _merge_object_list(self, target: List[Any], incoming: Iterable[Any], mode: str) -> None:
        for item in incoming:
            normalized = _normalize_object(item)
            if not normalized:
                continue

            name = _object_name(normalized)
            existing = _find_object(target, name)
            if existing is None:
                target.append(normalized)
                continue

            for field, value in normalized.items():
                if field == "attributes":
                    existing[field] = _merge_unique(existing.get(field, []), ensure_list(value))
                elif field == "must_preserve":
                    existing[field] = bool(value) or bool(existing.get(field))
                elif value not in (None, "", [], {}):
                    existing[field] = value

    def _apply_removals(self, memory: Dict[str, Any], removals: Dict[str, Any]) -> None:
        if not isinstance(removals, dict):
            return

        for key in ("main_subjects", "objects"):
            if key in removals:
                names = {_name_from_removal(item) for item in ensure_list(removals[key])}
                names.discard(None)
                memory[key] = [
                    item
                    for item in memory[key]
                    if _object_name(item).lower() not in {str(name).lower() for name in names}
                ]

        for key in ("scene", "style"):
            values = removals.get(key)
            if isinstance(values, list):
                for field in values:
                    memory[key].pop(str(field), None)
            elif isinstance(values, dict):
                for field in values:
                    memory[key].pop(str(field), None)

        for key in ("constraints", "negative_constraints"):
            if key in removals:
                to_remove = {str(item).lower() for item in ensure_list(removals[key])}
                memory[key] = [item for item in memory[key] if str(item).lower() not in to_remove]

    @staticmethod
    def _extend_unique_strings(target: List[str], incoming: Iterable[Any]) -> None:
        for item in incoming:
            if item is None:
                continue
            text = str(item).strip()
            if text and text.lower() not in {str(existing).lower() for existing in target}:
                target.append(text)


def _clean_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in value.items() if v not in (None, "", [], {})}


def _normalize_object(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {"name": item}
    if not isinstance(item, dict):
        return {}
    copied = deepcopy(item)
    if "name" not in copied and len(copied) == 1:
        name, value = next(iter(copied.items()))
        if isinstance(value, dict):
            copied = {"name": name, **value}
    if "attributes" in copied and not isinstance(copied["attributes"], list):
        copied["attributes"] = ensure_list(copied["attributes"])
    return _clean_dict(copied)


def _object_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name", "")).strip()
    return str(item).strip()


def _find_object(items: List[Any], name: str) -> Optional[Dict[str, Any]]:
    lowered = name.lower()
    for item in items:
        if isinstance(item, dict) and _object_name(item).lower() == lowered:
            return item
    return None


def _merge_unique(existing: Any, incoming: Iterable[Any]) -> List[Any]:
    result = ensure_list(existing)
    known = {str(item).lower() for item in result}
    for item in incoming:
        text = str(item).strip()
        if text and text.lower() not in known:
            result.append(text)
            known.add(text.lower())
    return result


def _name_from_removal(item: Any) -> Optional[str]:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("name")
    return None

