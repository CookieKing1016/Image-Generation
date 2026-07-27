"""Mask creation and conservative source/candidate compositing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Tuple


def combine_masks(mask_paths: Iterable[Path], destination: Path) -> Path | None:
    """Union task-level masks while preserving their soft alpha edges."""
    from PIL import Image, ImageChops

    paths = [Path(path) for path in mask_paths if Path(path).is_file()]
    if not paths:
        return None
    with Image.open(paths[0]) as first:
        combined = first.convert("L")
    for path in paths[1:]:
        with Image.open(path) as image:
            combined = ImageChops.lighter(combined, image.convert("L").resize(combined.size))
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.save(destination)
    return destination


def create_bbox_mask(
    image_path: Path,
    bbox_1000: Tuple[int, int, int, int],
    destination: Path,
    feather_px: Optional[int] = None,
    padding_ratio: float = 0.05,
) -> Path:
    """Build a soft local-edit mask with a small context band.

    A VLM box is an uncertain visual estimate, not a precise silhouette. The
    context band gives an editor room to rebuild object boundaries and shadows;
    the adaptive feather blends candidate pixels into the untouched source.
    Passing ``feather_px=0`` keeps deterministic tests and diagnostic masks
    hard-edged.
    """
    from PIL import Image, ImageDraw, ImageFilter

    with Image.open(image_path) as source:
        width, height = source.size
    left, top, right, bottom = bbox_1000
    pixel_box = (
        round(left / 1000 * width),
        round(top / 1000 * height),
        round(right / 1000 * width),
        round(bottom / 1000 * height),
    )
    pixel_box = _expand_box(pixel_box, width, height, padding_ratio)
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rectangle(pixel_box, fill=255)
    resolved_feather = _resolve_feather(pixel_box, width, height, feather_px)
    if resolved_feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=resolved_feather))
    destination.parent.mkdir(parents=True, exist_ok=True)
    mask.save(destination)
    return destination


def composite_masked_edit(source_path: Path, candidate_path: Path, mask_path: Path, destination: Path) -> Path:
    from PIL import Image

    with Image.open(source_path) as source, Image.open(candidate_path) as candidate, Image.open(mask_path) as mask:
        base = source.convert("RGB")
        edited = candidate.convert("RGB").resize(base.size)
        alpha = mask.convert("L").resize(base.size)
        result = Image.composite(edited, base, alpha)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.save(destination)
    return destination


def create_union_mask(
    image_path: Path,
    boxes_1000: Iterable[Tuple[int, int, int, int]],
    destination: Path,
    feather_px: Optional[int] = None,
    padding_ratio: float = 0.05,
) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    with Image.open(image_path) as source:
        width, height = source.size
    mask = Image.new("L", (width, height), 0)
    drawer = ImageDraw.Draw(mask)
    pixel_boxes = []
    for left, top, right, bottom in boxes_1000:
        pixel_box = _expand_box(
            (round(left / 1000 * width), round(top / 1000 * height), round(right / 1000 * width), round(bottom / 1000 * height)),
            width,
            height,
            padding_ratio,
        )
        pixel_boxes.append(pixel_box)
        drawer.rectangle(pixel_box, fill=255)
    resolved_feather = max((_resolve_feather(box, width, height, feather_px) for box in pixel_boxes), default=0)
    if resolved_feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=resolved_feather))
    destination.parent.mkdir(parents=True, exist_ok=True)
    mask.save(destination)
    return destination


def invert_mask(mask_path: Path, destination: Path) -> Path:
    from PIL import Image, ImageOps

    with Image.open(mask_path) as mask:
        inverted = ImageOps.invert(mask.convert("L"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        inverted.save(destination)
    return destination


def create_position_mask(image_path: Path, position: str, destination: Path, feather_px: Optional[int] = None) -> Path | None:
    normalized = str(position).lower()
    if "left" in normalized:
        box = (0, 150, 420, 850)
    elif "right" in normalized:
        box = (580, 150, 1000, 850)
    elif "top" in normalized or "upper" in normalized:
        box = (200, 0, 800, 420)
    elif "bottom" in normalized or "lower" in normalized:
        box = (200, 580, 800, 1000)
    elif "center" in normalized or "middle" in normalized:
        box = (280, 250, 720, 750)
    elif "beside" in normalized or "next to" in normalized or "旁边" in normalized or "侧边" in normalized:
        box = (120, 420, 880, 900)
    else:
        return None
    return create_bbox_mask(image_path, box, destination, feather_px=feather_px, padding_ratio=0.02)


def _expand_box(
    box: Tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    padding_ratio: float,
) -> Tuple[int, int, int, int]:
    left, top, right, bottom = box
    box_width = max(1, right - left)
    box_height = max(1, bottom - top)
    pad_x = round(box_width * max(0.0, padding_ratio))
    pad_y = round(box_height * max(0.0, padding_ratio))
    return (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image_width, right + pad_x),
        min(image_height, bottom + pad_y),
    )


def _resolve_feather(
    box: Tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    feather_px: Optional[int],
) -> int:
    if feather_px is not None:
        return max(0, int(feather_px))
    _, top, right, bottom = box
    left = box[0]
    target_scale = min(max(1, right - left), max(1, bottom - top))
    image_scale = min(image_width, image_height)
    return max(12, min(48, round(min(target_scale * 0.12, image_scale * 0.04))))
