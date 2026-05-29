"""Compose memory-aware prompts for text-to-image generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.schema import normalize_memory


@dataclass
class PromptBundle:
    positive: str
    negative: str

    @property
    def generation_prompt(self) -> str:
        if not self.negative:
            return self.positive
        return f"{self.positive}\nAvoid: {self.negative}"


class PromptComposer:
    def compose(self, memory: Dict[str, Any]) -> PromptBundle:
        memory = normalize_memory(memory)
        sections: List[str] = []

        subjects = [_object_to_text(item, main=True) for item in memory["main_subjects"]]
        subjects = [item for item in subjects if item]
        if subjects:
            sections.append("Main subject: " + "; ".join(subjects) + ".")

        objects = [_object_to_text(item, main=False) for item in memory["objects"]]
        objects = [item for item in objects if item]
        if objects:
            sections.append("Additional visible objects: " + "; ".join(objects) + ".")

        scene = _dict_to_phrase(memory["scene"])
        if scene:
            sections.append("Scene: " + scene + ".")

        style = _dict_to_phrase(memory["style"])
        if style:
            sections.append("Visual style: " + style + ".")

        if memory["constraints"]:
            sections.append("Must preserve: " + "; ".join(memory["constraints"]) + ".")

        if memory["current_turn_goal"]:
            sections.append("Current edit goal: " + memory["current_turn_goal"] + ".")

        sections.append("Create a coherent, high-quality image with clear composition and visible requested details.")
        positive = " ".join(sections)

        negative_parts = list(memory["negative_constraints"])
        negative_parts.extend(["low quality", "blurry details", "text artifacts", "unintended extra subjects"])
        negative = ", ".join(_dedupe(negative_parts))
        return PromptBundle(positive=positive, negative=negative)


def _object_to_text(item: Any, main: bool) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return ""

    parts = [str(item.get("name", "")).strip()]
    attributes = item.get("attributes")
    if isinstance(attributes, list) and attributes:
        parts.append("with " + ", ".join(str(attr) for attr in attributes))
    elif isinstance(attributes, str) and attributes:
        parts.append("with " + attributes)

    if item.get("pose"):
        parts.append("pose: " + str(item["pose"]))
    if item.get("position"):
        parts.append("position: " + str(item["position"]))
    if item.get("must_preserve"):
        parts.append("must remain visually consistent")

    text = ", ".join(part for part in parts if part)
    if main and text:
        return text
    return text


def _dict_to_phrase(value: Dict[str, Any]) -> str:
    parts = []
    for key, item in value.items():
        if item in (None, "", [], {}):
            continue
        pretty_key = key.replace("_", " ")
        parts.append(f"{pretty_key}: {item}")
    return "; ".join(parts)


def _dedupe(items: List[str]) -> List[str]:
    result = []
    known = set()
    for item in items:
        text = str(item).strip()
        if text and text.lower() not in known:
            result.append(text)
            known.add(text.lower())
    return result

