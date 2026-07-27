"""Shared schemas and JSON helpers for the first-stage pipeline."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Dict, List


MEMORY_KEYS = (
    "main_subjects",
    "objects",
    "scene",
    "style",
    "constraints",
    "negative_constraints",
    "current_turn_goal",
    "turn_history",
    "deleted_entities",
)

DELTA_KEYS = ("add", "update", "remove", "current_turn_goal", "reason")


def empty_memory() -> Dict[str, Any]:
    return {
        "main_subjects": [],
        "objects": [],
        "scene": {},
        "style": {},
        "constraints": [],
        "negative_constraints": [],
        "current_turn_goal": "",
        "turn_history": [],
        "deleted_entities": [],
    }


def normalize_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    normalized = empty_memory()
    if isinstance(memory, dict):
        normalized.update({k: deepcopy(memory.get(k, normalized[k])) for k in MEMORY_KEYS})

    for key in ("main_subjects", "objects", "constraints", "negative_constraints", "turn_history", "deleted_entities"):
        if not isinstance(normalized[key], list):
            normalized[key] = []

    for key in ("scene", "style"):
        if not isinstance(normalized[key], dict):
            normalized[key] = {}

    if not isinstance(normalized["current_turn_goal"], str):
        normalized["current_turn_goal"] = str(normalized["current_turn_goal"])

    _ensure_entity_metadata(normalized)
    return normalized


def _ensure_entity_metadata(memory: Dict[str, Any]) -> None:
    """Keep the legacy object lists while giving visual entities stable identity.

    The prompt and checklist pipeline still consumes ``main_subjects`` and
    ``objects`` directly.  Metadata therefore lives on each entity rather than
    replacing the existing memory shape, which keeps previous runs readable.
    """
    used_ids = set()
    for collection in ("main_subjects", "objects"):
        for item in memory[collection]:
            if isinstance(item, dict) and item.get("entity_id"):
                used_ids.add(str(item["entity_id"]))

    counters: Dict[str, int] = {}
    for collection in ("main_subjects", "objects"):
        for item in memory[collection]:
            if not isinstance(item, dict):
                continue
            entity_type = _entity_type(item.get("name", "entity"))
            if not item.get("entity_id"):
                counters[entity_type] = counters.get(entity_type, 0) + 1
                candidate = f"{entity_type}_{counters[entity_type]}"
                while candidate in used_ids:
                    counters[entity_type] += 1
                    candidate = f"{entity_type}_{counters[entity_type]}"
                item["entity_id"] = candidate
                used_ids.add(candidate)
            item["entity_type"] = str(item.get("entity_type") or entity_type)
            item["status"] = str(item.get("status") or "active")
            if not isinstance(item.get("preserve"), list):
                item["preserve"] = ensure_list(item.get("preserve"))
            if not isinstance(item.get("provenance"), list):
                item["provenance"] = ensure_list(item.get("provenance"))
            if not isinstance(item.get("attribute_slots"), dict):
                item["attribute_slots"] = {}


def _entity_type(name: Any) -> str:
    words = re.findall(r"[a-z0-9]+", str(name).lower())
    return words[-1] if words else "entity"


def empty_delta() -> Dict[str, Any]:
    return {
        "add": {},
        "update": {},
        "remove": {},
        "current_turn_goal": "",
        "reason": "",
    }


def normalize_delta(delta: Dict[str, Any]) -> Dict[str, Any]:
    normalized = empty_delta()
    if isinstance(delta, dict):
        normalized.update({k: deepcopy(delta.get(k, normalized[k])) for k in DELTA_KEYS})

    for key in ("add", "update", "remove"):
        if not isinstance(normalized[key], dict):
            normalized[key] = {}

    for key in ("current_turn_goal", "reason"):
        if normalized[key] is None:
            normalized[key] = ""
        elif not isinstance(normalized[key], str):
            normalized[key] = str(normalized[key])

    return normalized


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def extract_json_object(text: str) -> Dict[str, Any]:
    """Extract a JSON object from an LLM response.

    The model is asked to return strict JSON, but this parser accepts common
    fenced-code and surrounding-prose variants to keep the demo resilient.
    """
    if not isinstance(text, str):
        raise ValueError("Expected a string LLM response.")

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
