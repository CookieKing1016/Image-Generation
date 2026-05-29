"""Deterministic checklist generation from Visual Intent Memory."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from core.schema import normalize_memory


class ChecklistGenerator:
    def generate(self, memory: Dict[str, Any]) -> List[Dict[str, str]]:
        memory = normalize_memory(memory)
        items: List[Dict[str, str]] = []

        for subject in memory["main_subjects"]:
            name = _object_name(subject)
            if not name:
                continue
            items.append(_item(f"subject_{name}_exists", f"Is there a {name} as the main subject?", "yes", "object"))
            if isinstance(subject, dict):
                for attr in _as_list(subject.get("attributes")):
                    items.append(
                        _item(
                            f"subject_{name}_attr_{attr}",
                            f"Is the {name} visibly {attr}?",
                            "yes",
                            "attribute",
                        )
                    )
                if subject.get("pose"):
                    items.append(
                        _item(
                            f"subject_{name}_pose",
                            f"Is the {name} {subject['pose']}?",
                            "yes",
                            "pose",
                        )
                    )
                if subject.get("position"):
                    items.append(
                        _item(
                            f"subject_{name}_position",
                            f"Is the {name} positioned at/in {subject['position']}?",
                            "yes",
                            "spatial",
                        )
                    )

        for obj in memory["objects"]:
            name = _object_name(obj)
            if name:
                items.append(_item(f"object_{name}_exists", f"Is there a visible {name}?", "yes", "object"))

        for key, value in memory["scene"].items():
            if value not in (None, "", [], {}):
                question = f"Does the image show {value} for the {key.replace('_', ' ')}?"
                items.append(_item(f"scene_{key}", question, "yes", "scene"))

        for key, value in memory["style"].items():
            if value not in (None, "", [], {}):
                question = f"Does the image follow the {key.replace('_', ' ')} of {value}?"
                items.append(_item(f"style_{key}", question, "yes", "style"))

        for idx, constraint in enumerate(memory["constraints"], 1):
            items.append(_item(f"constraint_{idx}", f"Is this preserved: {constraint}?", "yes", "constraint"))

        for idx, constraint in enumerate(memory["negative_constraints"], 1):
            items.append(_item(f"negative_{idx}", f"Does the image contain this disallowed element: {constraint}?", "no", "negative_constraint"))

        return _dedupe_by_question(items)


def _item(item_id: str, question: str, target: str, item_type: str) -> Dict[str, str]:
    return {
        "id": _slug(item_id),
        "question": question,
        "target": target,
        "type": item_type,
    }


def _object_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name", "")).strip()
    return str(item).strip()


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()


def _dedupe_by_question(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    known = set()
    for item in items:
        key = item["question"].lower()
        if key not in known:
            result.append(item)
            known.add(key)
    return result

