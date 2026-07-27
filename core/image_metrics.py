"""Deterministic image comparison metrics for multi-turn editing traces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def compare_images(previous: Path, current: Path, mask_path: Path | None = None) -> Dict[str, Any]:
    """Compute global similarity and, when available, mask-outside locality."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        return {"available": False, "reason": f"Image metric dependencies are unavailable: {exc}"}

    with Image.open(previous) as old_image, Image.open(current) as new_image:
        size = (min(old_image.width, new_image.width, 384), min(old_image.height, new_image.height, 384))
        old_pixels = np.asarray(old_image.convert("RGB").resize(size), dtype=np.float32)
        new_pixels = np.asarray(new_image.convert("RGB").resize(size), dtype=np.float32)

    mae = float(np.mean(np.abs(old_pixels - new_pixels))) / 255.0
    similarity = max(0.0, min(1.0, 1.0 - mae))
    result: Dict[str, Any] = {
        "available": True,
        "metric_type": "global_pixel_similarity",
        "global_pixel_similarity": round(similarity, 4),
        "mean_absolute_difference": round(mae, 4),
        "edit_locality_available": False,
        "reason": "No segmentation mask is available; this is a global consistency proxy, not mask-outside locality.",
    }
    if mask_path and mask_path.is_file():
        with Image.open(mask_path) as image_mask:
            mask_pixels = np.asarray(image_mask.convert("L").resize(size), dtype=np.float32) / 255.0
        outside = 1.0 - mask_pixels
        outside_weight = float(np.sum(outside))
        if outside_weight > 0:
            outside_mae = float(np.sum(np.abs(old_pixels - new_pixels) * outside[:, :, None])) / (255.0 * 3 * outside_weight)
            result.update(
                {
                    "metric_type": "mask_outside_pixel_similarity",
                    "edit_locality_available": True,
                    "edit_locality": round(max(0.0, min(1.0, 1.0 - outside_mae)), 4),
                    "mask_coverage": round(float(np.mean(mask_pixels)), 4),
                    "reason": "Edit locality is pixel similarity outside the VLM-located mask.",
                }
            )
    return result
