"""VLM-based visual target localization for the local-editing MVP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.schema import extract_json_object
from core.task_graph import EditTask
from tools.siliconflow_client import SiliconFlowClient, first_message_text


LOCATOR_PROMPT = """You locate one already-visible visual target in an image.
Return strict JSON only:
{
  "found": true,
  "bbox_1000": [left, top, right, bottom],
  "reason": "short visual evidence"
}

Coordinates use a 0-1000 canvas. The bounding box must tightly cover the
visible target, with left < right and top < bottom. If the target is not
already visible, return found=false and an empty bbox_1000 list.
"""


@dataclass
class RegionLocation:
    found: bool
    bbox_1000: Optional[tuple[int, int, int, int]] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "found": self.found,
            "bbox_1000": list(self.bbox_1000) if self.bbox_1000 else [],
            "reason": self.reason,
        }


class RegionLocator:
    """Use the configured VLM to locate targets that exist in the source image."""

    def __init__(self, client: SiliconFlowClient):
        self.client = client

    def locate(self, image_path: Path, task: EditTask) -> RegionLocation:
        if task.operation not in {"change_attribute", "remove_object", "move_object"}:
            return RegionLocation(False, reason=f"{task.operation} has no guaranteed pre-existing target.")
        target = task.affected_region or task.target
        return self.locate_target(image_path, target, task.affected_region, task.operation)

    def locate_target(
        self,
        image_path: Path,
        target: str,
        region_hint: str = "",
        operation: str = "change_attribute",
    ) -> RegionLocation:
        prompt = (
            f"{LOCATOR_PROMPT}\n\n"
            f"Task operation: {operation}\n"
            f"Target to locate: {target}\n"
            f"Visual region hint: {region_hint}\n"
            "Locate the existing target before the requested edit."
        )
        response = self.client.vision_completion(prompt, image_path, temperature=0.0, max_tokens=400)
        raw = extract_json_object(first_message_text(response))
        return _normalize_location(raw)


def _normalize_location(raw: Dict[str, Any]) -> RegionLocation:
    if not bool(raw.get("found", False)):
        return RegionLocation(False, reason=str(raw.get("reason", "Target was not found.")))
    values = raw.get("bbox_1000", [])
    if not isinstance(values, list) or len(values) != 4:
        return RegionLocation(False, reason="Locator returned an invalid bounding box.")
    try:
        left, top, right, bottom = (int(round(float(value))) for value in values)
    except (TypeError, ValueError):
        return RegionLocation(False, reason="Locator bounding box was not numeric.")
    left, top, right, bottom = (max(0, min(1000, value)) for value in (left, top, right, bottom))
    if right <= left or bottom <= top:
        return RegionLocation(False, reason="Locator bounding box had invalid dimensions.")
    return RegionLocation(True, (left, top, right, bottom), str(raw.get("reason", "")))
