"""Deterministic checklist generation from Visual Intent Memory."""

from __future__ import annotations

import re
import hashlib
from typing import Any, Dict, List

from core.schema import normalize_memory


class ChecklistGenerator:
    def generate(self, memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        memory = normalize_memory(memory)
        items: List[Dict[str, Any]] = []

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
            is_superseded = str(constraint).startswith("The superseded visual attribute must not remain visible:")
            items.append(
                _item(
                    f"negative_{idx}",
                    f"Does the image contain this disallowed element: {constraint}?",
                    "no",
                    "negative_constraint",
                    source="history" if is_superseded else "",
                    critical=is_superseded,
                    drift_type="old_attribute_residual" if is_superseded else "",
                )
            )

        return _dedupe_by_question(items)


def _item(
    item_id: str,
    question: str,
    target: str,
    item_type: str,
    source: str = "",
    critical: bool = False,
    drift_type: str = "",
) -> Dict[str, Any]:
    return {
        "id": _slug(item_id),
        "question": question,
        "target": target,
        "type": item_type,
        "source": source,
        "critical": critical,
        "drift_type": drift_type,
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
    text = str(value)
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_").lower()
    # Keep IDs readable for English while preventing Chinese/non-ASCII items
    # from collapsing to the same empty or partial slug in SQLite.
    if not slug or any(ord(char) > 127 for char in text):
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug or 'item'}_{digest}"
    return slug


def _dedupe_by_question(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    known = set()
    for item in items:
        key = item["question"].lower()
        if key not in known:
            result.append(item)
            known.add(key)
    return result
