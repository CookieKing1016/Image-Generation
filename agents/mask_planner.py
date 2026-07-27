"""Select a transparent mask strategy for each planned image operation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from agents.region_locator import RegionLocator
from core.mask_utils import combine_masks, create_bbox_mask, create_position_mask, create_union_mask, invert_mask
from core.task_graph import EditTask, TaskGraph
from tools.segmenter import Segmenter, UnavailableSegmenter


@dataclass
class MaskPlan:
    mask_path: Path | None = None
    backend: str = "none"
    reason: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    task_masks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mask_path": str(self.mask_path or ""),
            "backend": self.backend,
            "reason": self.reason,
            "events": self.events,
            "task_masks": self.task_masks,
        }


class MaskPlanner:
    def __init__(self, locator: RegionLocator, segmenter: Segmenter | None = None):
        self.locator = locator
        self.segmenter = segmenter or UnavailableSegmenter()

    def plan(self, image_path: Path, task_graph: TaskGraph, memory: Dict[str, Any], directory: Path) -> MaskPlan:
        if any(task.operation == "replace_object" for task in task_graph.tasks):
            replacement = next(task for task in task_graph.tasks if task.operation == "replace_object")
            return MaskPlan(
                reason="Whole-subject replacement uses reference editing to preserve natural silhouette and lighting.",
                events=[{"task_id": replacement.task_id, "route": "reference_edit"}],
            )

        task_masks: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        for task in task_graph.tasks:
            if task.operation in {"change_attribute", "remove_object", "move_object"}:
                planned = self._target_mask(image_path, task, directory)
            elif task.operation == "add_object":
                position = str(task.metadata.get("position", ""))
                destination = directory / f"{task.task_id}_mask.png"
                mask_path = create_position_mask(image_path, position, destination) if position else None
                planned = MaskPlan(
                    mask_path,
                    "position_prior" if mask_path else "none",
                    f"Placed new object using explicit position '{position}'." if mask_path else "No reliable placement prior.",
                    [{"task_id": task.task_id, "position": position, "found": bool(mask_path)}],
                )
            elif task.operation == "change_background_or_style":
                planned = self._background_mask(image_path, memory, directory, task.task_id)
            else:
                continue
            events.extend(planned.events)
            if planned.mask_path:
                task_masks.append(
                    {
                        "task_id": task.task_id,
                        "operation": task.operation,
                        "target": task.target,
                        "path": str(planned.mask_path),
                        "backend": planned.backend,
                        "reason": planned.reason,
                    }
                )

        union_path = combine_masks((Path(item["path"]) for item in task_masks), directory / "mask.png")
        if not union_path:
            return MaskPlan(reason="No reliable local mask strategy for any planned task.", events=events)
        backends = sorted({str(item["backend"]) for item in task_masks})
        return MaskPlan(
            union_path,
            "+".join(backends),
            f"Union of {len(task_masks)} task-level masks.",
            events,
            task_masks,
        )

    def _target_mask(self, image_path: Path, task: EditTask, directory: Path) -> MaskPlan:
        location = self.locator.locate(image_path, task)
        event = {"task_id": task.task_id, **location.to_dict()}
        if not location.found or not location.bbox_1000:
            return MaskPlan(reason=location.reason, events=[event])
        if self.segmenter.available:
            try:
                mask_path = self.segmenter.segment_box(
                    image_path,
                    location.bbox_1000,
                    directory / f"{task.task_id}_sam2_mask.png",
                )
                event["segmentation_backend"] = self.segmenter.backend_name
                return MaskPlan(mask_path, self.segmenter.backend_name, location.reason, [event])
            except Exception as exc:
                event["segmentation_fallback"] = {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
        mask_path = create_bbox_mask(image_path, location.bbox_1000, directory / f"{task.task_id}_mask.png")
        return MaskPlan(mask_path, "vlm_bbox", location.reason, [event])

    def _background_mask(self, image_path: Path, memory: Dict[str, Any], directory: Path, task_id: str) -> MaskPlan:
        protection_masks = []
        boxes = []
        events = []
        for subject in memory.get("main_subjects", []):
            if not isinstance(subject, dict):
                continue
            target = str(subject.get("name", "")).strip()
            if not target:
                continue
            location = self.locator.locate_target(image_path, target, target, "protect_subject")
            events.append({"target": target, **location.to_dict()})
            if location.found and location.bbox_1000:
                if self.segmenter.available:
                    try:
                        protection_masks.append(
                            self.segmenter.segment_box(
                                image_path,
                                location.bbox_1000,
                                directory / f"{task_id}_{len(protection_masks) + 1:02d}_sam2_subject.png",
                            )
                        )
                        events[-1]["segmentation_backend"] = self.segmenter.backend_name
                        continue
                    except Exception as exc:
                        events[-1]["segmentation_fallback"] = {
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                boxes.append(location.bbox_1000)
        if protection_masks:
            if boxes:
                protection_masks.append(
                    create_union_mask(
                        image_path,
                        boxes,
                        directory / f"{task_id}_bbox_subjects.png",
                    )
                )
            protection = combine_masks(
                protection_masks,
                directory / f"{task_id}_subject_protection_mask.png",
            )
            if not protection:
                return MaskPlan(reason="Subject segmentation did not produce a protection mask.", events=events)
            background_mask = invert_mask(protection, directory / f"{task_id}_mask.png")
            return MaskPlan(
                background_mask,
                self.segmenter.backend_name,
                "Inverted union of segmented subject silhouettes.",
                events,
            )
        if not boxes:
            return MaskPlan(reason="No main subject could be located for background protection.", events=events)
        protection = create_union_mask(image_path, boxes, directory / f"{task_id}_subject_protection_mask.png")
        background_mask = invert_mask(protection, directory / f"{task_id}_mask.png")
        return MaskPlan(background_mask, "vlm_bbox_subject_protection", "Inverted union of located subject boxes.", events)
