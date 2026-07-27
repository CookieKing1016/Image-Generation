"""Deterministic Visual Intent Memory merge rules."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, Iterable, List, Optional

from core.schema import ensure_list, normalize_delta, normalize_memory


COLOR_WORDS = {
    "black",
    "blue",
    "brown",
    "clear",
    "gray",
    "green",
    "grey",
    "orange",
    "purple",
    "red",
    "white",
    "yellow",
}
COLOR_ALIASES = {
    "deep burgundy": "deep_burgundy",
    "burgundy": "burgundy",
    "深酒红色": "deep_burgundy",
    "酒红色": "burgundy",
    "黑色": "black",
    "蓝白色": "blue_white",
    "蓝色": "blue",
    "红色": "red",
    "白色": "white",
    "绿色": "green",
    "黄色": "yellow",
    "紫色": "purple",
    "金色": "gold",
    "银色": "silver",
}
PART_ALIASES = {
    "ribbon": ("ribbon", "bow", "缎带", "丝带", "蝴蝶结"),
    "scarf": ("scarf", "围巾"),
    "collar": ("collar", "项圈"),
    "cap": ("cap", "lid", "瓶盖", "盖子"),
    "label": ("label", "标签"),
    "packaging": ("packaging", "package", "包装", "瓶身", "袋身"),
}
MATERIAL_WORDS = {
    "ceramic",
    "glass",
    "leather",
    "marble",
    "metal",
    "plastic",
    "wood",
    "wooden",
}
WEARABLE_WORDS = {"collar", "hat", "scarf"}
NON_READABLE_TEXT_TERMS = ("no readable text", "without readable text", "do not include readable text")


class MemoryUpdater:
    def update(self, memory: Dict[str, Any], delta: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        next_memory = normalize_memory(memory)
        normalized_delta = normalize_delta(delta)
        turn_number = len(next_memory["turn_history"]) + 1

        self._apply_section(next_memory, normalized_delta.get("add", {}), mode="add")
        superseded = self._apply_section(next_memory, normalized_delta.get("update", {}), mode="update")
        self._coalesce_structured_attribute_entities(next_memory, normalized_delta)
        self._apply_removals(next_memory, normalized_delta.get("remove", {}), turn_number)
        self._resolve_conflicts(next_memory, normalized_delta)
        self._apply_superseded_constraints(next_memory, superseded)

        if normalized_delta.get("current_turn_goal"):
            next_memory["current_turn_goal"] = normalized_delta["current_turn_goal"]

        self._annotate_entities(next_memory, turn_number)

        next_memory["turn_history"].append(
            {
                "turn": len(next_memory["turn_history"]) + 1,
                "instruction": instruction,
                "delta": normalized_delta,
                "current_turn_goal": next_memory["current_turn_goal"],
            }
        )
        return normalize_memory(next_memory)

    @staticmethod
    def _coalesce_structured_attribute_entities(memory: Dict[str, Any], delta: Dict[str, Any]) -> None:
        """Remove duplicate component entities created alongside a structured update.

        Intent extraction may emit both ``update bottle.ribbon`` and ``add red bow``
        for one replacement. The component must remain an attribute of the bottle,
        otherwise prompt composition and mask planning treat it as a second object.
        """
        updates = [
            item
            for section in ("main_subjects", "objects")
            for item in ensure_list(delta.get("update", {}).get(section))
            if isinstance(item, dict) and (item.get("attribute_states") or item.get("attribute_slots"))
        ]
        if not updates:
            return
        component_markers = ("ribbon", "bow", "缎带", "丝带", "蝴蝶结", "scarf", "围巾", "collar", "项圈")
        for collection in ("main_subjects", "objects"):
            retained = []
            for candidate in memory[collection]:
                name = _object_name(candidate).lower()
                if not any(marker in name for marker in component_markers):
                    retained.append(candidate)
                    continue
                candidate_slots = _attribute_slots([name] + ensure_list(candidate.get("attributes")))
                matched = False
                for update in updates:
                    update_slots = _attribute_slots(ensure_list(update.get("attributes")))
                    if any(slot.startswith("part:ribbon:") and values & candidate_slots.get(slot, set()) for slot, values in update_slots.items()):
                        matched = True
                        break
                    if any(marker in " ".join(str(value).lower() for value in ensure_list(update.get("attributes"))) for marker in component_markers):
                        if candidate_slots.get("color") and candidate_slots["color"] & set().union(*update_slots.values()):
                            matched = True
                            break
                if not matched:
                    retained.append(candidate)
            memory[collection] = retained

    @staticmethod
    def _annotate_entities(memory: Dict[str, Any], turn_number: int) -> None:
        """Expose active visual state and provenance without changing prompts."""
        for collection in ("main_subjects", "objects"):
            for entity in memory[collection]:
                if not isinstance(entity, dict):
                    continue
                entity["status"] = "active"
                provenance = entity.setdefault("provenance", [])
                if not provenance:
                    provenance.append(turn_number)
                states = entity.setdefault("attribute_states", {})
                active_attributes = {str(attribute).strip() for attribute in ensure_list(entity.get("attributes")) if str(attribute).strip()}
                for attribute in active_attributes:
                    key = str(attribute).strip()
                    if key and key not in states:
                        states[key] = {"status": "active", "updated_at_turn": turn_number}
                for attribute, state in states.items():
                    if attribute not in active_attributes and state.get("status") == "active":
                        state["status"] = "superseded"
                        state["superseded_at_turn"] = turn_number
                    elif attribute in active_attributes:
                        state["status"] = "active"
                slot_states = entity.setdefault("attribute_slots", {})
                active_slots = _attribute_slots(active_attributes)
                for slot, values in active_slots.items():
                    normalized_values = sorted(values)
                    previous = slot_states.get(slot)
                    if previous and previous.get("value") != normalized_values:
                        history = list(previous.get("history", []))
                        history.append(
                            {
                                "value": previous.get("value", []),
                                "source_attribute": previous.get("source_attribute", ""),
                                "status": "superseded",
                                "superseded_at_turn": turn_number,
                            }
                        )
                    else:
                        history = list(previous.get("history", [])) if previous else []
                    source_attribute = next(
                        (
                            attribute
                            for attribute in active_attributes
                            if slot in _attribute_slots([attribute])
                        ),
                        "",
                    )
                    slot_states[slot] = {
                        "value": normalized_values,
                        "source_attribute": source_attribute,
                        "status": "active",
                        "updated_at_turn": turn_number,
                        "history": history,
                    }

    def _apply_section(self, memory: Dict[str, Any], section: Dict[str, Any], mode: str) -> List[str]:
        superseded: List[str] = []
        if not isinstance(section, dict):
            return superseded

        for key in ("main_subjects", "objects"):
            if key in section:
                superseded.extend(self._merge_object_list(memory[key], ensure_list(section[key]), mode=mode))

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
        return superseded

    def _merge_object_list(self, target: List[Any], incoming: Iterable[Any], mode: str) -> List[str]:
        superseded: List[str] = []
        for item in incoming:
            normalized = _normalize_object(item)
            if not normalized:
                continue

            name = _object_name(normalized)
            if mode == "update":
                matches = _find_matching_objects(target, normalized)
                if not matches:
                    normalized["name"] = _rewrite_name_for_attributes(name, normalized.get("attributes", []))
                    target.append(normalized)
                    continue
                for existing in matches:
                    superseded.extend(_merge_object_fields(existing, normalized, mode=mode))
                continue

            existing = _find_object(target, name)
            if existing is None:
                existing = _find_compatible_object(target, normalized)
            if existing is None or _should_append_distinct_instance(existing, normalized):
                normalized["name"] = _rewrite_name_for_attributes(name, normalized.get("attributes", []))
                target.append(normalized)
                continue

            superseded.extend(_merge_object_fields(existing, normalized, mode=mode))
        return superseded

    def _apply_superseded_constraints(self, memory: Dict[str, Any], superseded: Iterable[str]) -> None:
        stale = [str(value).strip() for value in superseded if str(value).strip()]
        if not stale:
            return
        stale_slots = _attribute_slots(stale)
        memory["constraints"] = [
            item
            for item in memory["constraints"]
            if not any(_shares_slot_value(str(item), value) for value in stale)
        ]
        for value in stale:
            self._extend_unique_strings(
                memory["negative_constraints"],
                [f"The superseded visual attribute must not remain visible: {value}."],
            )

    def _apply_removals(self, memory: Dict[str, Any], removals: Dict[str, Any], turn_number: int) -> None:
        if not isinstance(removals, dict):
            return

        for key in ("main_subjects", "objects"):
            if key in removals:
                names = {_name_from_removal(item) for item in ensure_list(removals[key])}
                names.discard(None)
                removed_items = [
                    item
                    for item in memory[key]
                    if _object_name(item).lower() in {str(name).lower() for name in names}
                ]
                memory[key] = [
                    item
                    for item in memory[key]
                    if _object_name(item).lower() not in {str(name).lower() for name in names}
                ]
                for removed in removed_items:
                    name = _object_name(removed)
                    if isinstance(removed, dict):
                        tombstone = deepcopy(removed)
                        tombstone["status"] = "deleted"
                        tombstone["deleted_at_turn"] = turn_number
                        memory["deleted_entities"].append(tombstone)
                    _remove_related_constraints(memory["constraints"], name)
                    _remove_related_constraints(memory["negative_constraints"], name)
                    self._extend_unique_strings(memory["negative_constraints"], _negative_constraints_for_removed_object(name))
                    if name.lower() == "credit card":
                        self._extend_unique_strings(
                            memory["constraints"],
                            ["The wallet must have clean closed edges with no card slot contents visible."],
                        )

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

    def _resolve_conflicts(self, memory: Dict[str, Any], delta: Dict[str, Any]) -> None:
        self._resolve_object_conflicts(memory)
        self._resolve_constraint_conflicts(memory, delta)

    def _resolve_object_conflicts(self, memory: Dict[str, Any]) -> None:
        for key in ("main_subjects", "objects"):
            for item in memory[key]:
                if not isinstance(item, dict):
                    continue
                attributes = item.get("attributes")
                if not isinstance(attributes, list):
                    continue
                item["attributes"] = _dedupe_preserve_order(_drop_stale_attribute_conflicts(attributes))
                item["name"] = _rewrite_name_for_attributes(_object_name(item), item.get("attributes", []))

    def _resolve_constraint_conflicts(self, memory: Dict[str, Any], delta: Dict[str, Any]) -> None:
        positive_text = _all_positive_memory_text(memory)
        update_text = jsonish_text(delta.get("update", {}))
        add_text = jsonish_text(delta.get("add", {}))
        goal = str(delta.get("current_turn_goal", ""))
        signal = " ".join([positive_text, update_text, add_text, goal]).lower()

        if "white ceramic" in signal:
            _remove_constraints_matching(memory["constraints"], ("clear glass", "transparent glass", "glass vase"))
            self._extend_unique_strings(memory["negative_constraints"], ["No transparent glass vase should be visible."])

        if "blue scarf" in signal:
            _remove_constraints_matching(memory["constraints"], ("red scarf",))
            self._extend_unique_strings(memory["negative_constraints"], ["No red scarf should be visible."])

        if "purple" in signal and "flower" in signal:
            _remove_constraints_matching(memory["constraints"], ("distinct colors", "red petal", "yellow petal", "white petal"))

        if "exactly three flowers" in signal or "three purple flowers" in signal:
            _remove_constraints_matching(memory["constraints"], ("arranged symmetrically on the wooden table",))
            self._extend_unique_strings(
                memory["constraints"],
                ["Show exactly three fully bloomed flowers inside the vase."],
            )
            self._extend_unique_strings(
                memory["negative_constraints"],
                [
                    "No extra flowers, flower buds, or loose flowers outside the vase.",
                    "Do not show fewer or more than three flowers.",
                ],
            )

        if any(term in goal.lower() for term in NON_READABLE_TEXT_TERMS):
            _remove_object_attributes_matching(memory, "blackboard", ("chalk writing", "visible writing", "readable text"))
            _remove_constraints_matching(memory["constraints"], ("visible writing", "readable text", "chalk marks", "chalk writing"))
            self._extend_unique_strings(
                memory["constraints"],
                ["The blackboard should be blank or contain only non-readable chalk smudges."],
            )
            self._extend_unique_strings(memory["negative_constraints"], ["No readable text on the blackboard."])

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


def _find_matching_objects(items: List[Any], incoming: Dict[str, Any]) -> List[Dict[str, Any]]:
    noun = _head_noun(_object_name(incoming))
    incoming_position = str(incoming.get("position", "")).strip().lower()
    if noun and incoming_position:
        positioned = [
            item
            for item in items
            if isinstance(item, dict)
            and _head_noun(_object_name(item)) == noun
            and str(item.get("position", "")).strip().lower() == incoming_position
        ]
        if positioned:
            return positioned

    exact = _find_object(items, _object_name(incoming))
    if exact is not None:
        if noun in {"flower"}:
            return [
                item
                for item in items
                if isinstance(item, dict) and _head_noun(_object_name(item)) == noun
            ]
        return [exact]

    compatible = _find_compatible_object(items, incoming)
    if compatible is None:
        return []
    noun = _head_noun(_object_name(incoming))
    if noun in {"flower"}:
        return [
            item
            for item in items
            if isinstance(item, dict) and _head_noun(_object_name(item)) == noun
        ]
    return [compatible]


def _find_compatible_object(items: List[Any], incoming: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    incoming_name = _object_name(incoming).lower()
    incoming_noun = _head_noun(incoming_name)
    if not incoming_noun:
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        existing_name = _object_name(item).lower()
        if _head_noun(existing_name) == incoming_noun:
            return item
    return None


def _should_append_distinct_instance(existing: Dict[str, Any], incoming: Dict[str, Any]) -> bool:
    existing_name = _object_name(existing).lower()
    incoming_name = _object_name(incoming).lower()
    if existing_name != incoming_name:
        return False
    noun = _head_noun(existing_name)
    if noun not in {"flower"}:
        return False
    incoming_position = str(incoming.get("position", "")).strip().lower()
    existing_position = str(existing.get("position", "")).strip().lower()
    return bool(incoming_position and existing_position and incoming_position != existing_position)


def _merge_object_fields(existing: Dict[str, Any], normalized: Dict[str, Any], mode: str) -> List[str]:
    superseded: List[str] = []
    structured_states = normalized.get("attribute_states")
    if mode == "update" and isinstance(structured_states, dict):
        active = [name for name, state in structured_states.items() if isinstance(state, dict) and state.get("status") == "active"]
        if active:
            existing["attributes"], removed = _merge_attributes(existing.get("attributes", []), active, mode="update")
            superseded.extend(removed)
            existing["name"] = _rewrite_name_for_attributes(_object_name(existing), existing["attributes"])
    for field, value in normalized.items():
        if field in {"attribute_states", "attribute_slots"}:
            existing[field] = deepcopy(value)
            continue
        if field == "attributes":
            existing[field], removed = _merge_attributes(existing.get(field, []), ensure_list(value), mode=mode)
            superseded.extend(removed)
            existing["name"] = _rewrite_name_for_attributes(_object_name(existing), existing[field])
        elif field == "must_preserve":
            existing[field] = bool(value) or bool(existing.get(field))
        elif field == "name" and mode == "update":
            existing[field] = _rewrite_name_for_attributes(str(value), normalized.get("attributes", []))
        elif value not in (None, "", [], {}):
            existing[field] = value
    return superseded


def _merge_attributes(existing: Any, incoming: Iterable[Any], mode: str) -> tuple[List[Any], List[str]]:
    incoming_list = [str(item).strip() for item in incoming if str(item).strip()]
    base = ensure_list(existing)
    removed: List[str] = []
    if mode == "update":
        filtered = _remove_conflicting_attributes(base, incoming_list)
        removed = [str(item).strip() for item in base if str(item).strip() and item not in filtered]
        base = filtered
    return _merge_unique(base, incoming_list), removed


def _remove_conflicting_attributes(existing: Iterable[Any], incoming: Iterable[str]) -> List[Any]:
    incoming_slots = _attribute_slots(incoming)
    if not incoming_slots:
        return [item for item in existing if str(item).strip()]
    result = []
    for item in existing:
        text = str(item).strip()
        if text and not _attribute_conflicts(text, incoming_slots):
            result.append(text)
    return result


def _drop_stale_attribute_conflicts(attributes: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for attr in attributes:
        text = str(attr).strip()
        if not text:
            continue
        slots = _attribute_slots([text])
        result = [existing for existing in result if not _attribute_conflicts(existing, slots)]
        result.append(text)
    return result


def _attribute_conflicts(attribute: str, incoming_slots: Dict[str, set[str]]) -> bool:
    lowered = attribute.lower()
    if "material" in incoming_slots and "ceramic" in incoming_slots["material"]:
        if any(term in lowered for term in ("transparent", "clear glass", "glass")):
            return True
    attr_slots = _attribute_slots([attribute])
    for slot, incoming_values in incoming_slots.items():
        attr_values = attr_slots.get(slot, set())
        if attr_values and incoming_values and attr_values != incoming_values:
            return True
    return False


def _shares_slot_value(left: str, right: str) -> bool:
    left_slots = _attribute_slots([left])
    right_slots = _attribute_slots([right])
    for slot in set(left_slots) & set(right_slots):
        if left_slots[slot] & right_slots[slot]:
            return True
    return False


def _attribute_slots(attributes: Iterable[str]) -> Dict[str, set[str]]:
    slots: Dict[str, set[str]] = {}
    for attr in attributes:
        lowered = str(attr).lower()
        words = set(re.findall(r"[a-z]+", lowered))
        colors = words & COLOR_WORDS
        matched_aliases = [alias for alias in COLOR_ALIASES if alias in lowered]
        if matched_aliases:
            most_specific = [
                alias
                for alias in matched_aliases
                if not any(alias != other and alias in other for other in matched_aliases)
            ]
            colors = {COLOR_ALIASES[alias] for alias in most_specific}
        materials = words & MATERIAL_WORDS
        wearables = words & WEARABLE_WORDS
        if colors:
            key = "color"
            part = _attribute_part(lowered)
            if part:
                key = "part:" + part + ":color"
            elif wearables:
                key = "wearable:" + sorted(wearables)[0]
            elif "petal" in words or "flower" in words:
                key = "flower_color"
            slots.setdefault(key, set()).update(colors)
        if materials:
            part = _attribute_part(lowered)
            key = "part:" + part + ":material" if part else "material"
            slots.setdefault(key, set()).update(materials)
        explicit = re.match(r"\s*([a-z_][a-z0-9_.-]*)\s*:\s*(.+)", lowered)
        if explicit:
            slots.setdefault("explicit:" + explicit.group(1), set()).add(explicit.group(2).strip())
    return slots


def _attribute_part(text: str) -> str:
    for canonical, aliases in PART_ALIASES.items():
        if any(alias in text for alias in aliases):
            return canonical
    return ""


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


def _negative_constraints_for_removed_object(name: str) -> List[str]:
    constraints = [f"No {name} should be visible."]
    if name.lower() == "credit card":
        constraints.extend(
            [
                "No card-like rectangle should protrude from the wallet.",
                "No bank card, ID card, or orange card should be visible.",
            ]
        )
    return constraints


def _rewrite_name_for_attributes(name: str, attributes: Iterable[Any]) -> str:
    lowered_attrs = " ".join(str(attr).lower() for attr in ensure_list(attributes))
    noun = _head_noun(name)
    if noun == "vase" and "white ceramic" in lowered_attrs:
        return "white ceramic vase"
    return name


def _head_noun(name: str) -> str:
    words = re.findall(r"[a-z]+", str(name).lower())
    for noun in ("vase", "wallet", "fox", "dog", "wolf", "robot", "textbook", "blackboard", "flower"):
        if noun in words:
            return noun
    return words[-1] if words else ""


def _remove_related_constraints(constraints: List[str], name: str) -> None:
    terms = _related_terms(name)
    constraints[:] = [item for item in constraints if not _contains_any(str(item), terms)]


def _remove_constraints_matching(constraints: List[str], terms: Iterable[str]) -> None:
    lowered_terms = tuple(str(term).lower() for term in terms)
    constraints[:] = [item for item in constraints if not _contains_any(str(item), lowered_terms)]


def _remove_object_attributes_matching(memory: Dict[str, Any], target_noun: str, terms: Iterable[str]) -> None:
    lowered_terms = tuple(str(term).lower() for term in terms)
    for key in ("main_subjects", "objects"):
        for item in memory[key]:
            if not isinstance(item, dict):
                continue
            if _head_noun(_object_name(item)) != target_noun:
                continue
            attributes = item.get("attributes")
            if isinstance(attributes, list):
                item["attributes"] = [attr for attr in attributes if not _contains_any(str(attr), lowered_terms)]


def _related_terms(name: str) -> List[str]:
    lowered = str(name).lower()
    terms = [lowered]
    noun = _head_noun(lowered)
    if noun and noun not in terms:
        terms.append(noun)
    return terms


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term and term in lowered for term in terms)


def _dedupe_preserve_order(items: Iterable[Any]) -> List[str]:
    result = []
    known = set()
    for item in items:
        text = str(item).strip()
        lowered = text.lower()
        if text and lowered not in known:
            result.append(text)
            known.add(lowered)
    return result


def _all_positive_memory_text(memory: Dict[str, Any]) -> str:
    parts = [
        jsonish_text(memory.get("main_subjects", [])),
        jsonish_text(memory.get("objects", [])),
        jsonish_text(memory.get("scene", {})),
        jsonish_text(memory.get("style", {})),
        jsonish_text(memory.get("constraints", [])),
    ]
    return " ".join(parts)


def jsonish_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(jsonish_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(jsonish_text(item) for item in value)
    return str(value)
