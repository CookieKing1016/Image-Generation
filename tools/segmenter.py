"""Optional silhouette segmentation behind a small provider-neutral boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Tuple

from tools.config import Settings


Box1000 = Tuple[int, int, int, int]


class Segmenter(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def backend_name(self) -> str: ...

    def segment_box(self, image_path: Path, bbox_1000: Box1000, destination: Path) -> Path: ...


class Sam2BoxSegmenter:
    """Refine a VLM-proposed box into a SAM2 silhouette mask.

    Model imports and initialization are lazy so the normal demo remains usable
    without the heavy local SAM2 runtime.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._predictor = None

    @property
    def backend_name(self) -> str:
        return "sam2_box_prompt"

    @property
    def available(self) -> bool:
        if self.settings.segmentation_backend not in {"auto", "sam2"}:
            return False
        checkpoint = Path(self.settings.sam2_checkpoint).expanduser()
        if not self.settings.sam2_model_config or not checkpoint.is_file():
            return False
        try:
            import sam2  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def segment_box(self, image_path: Path, bbox_1000: Box1000, destination: Path) -> Path:
        if not self.available:
            raise RuntimeError("SAM2 is unavailable: configure its package, checkpoint, and model config.")

        import numpy as np
        from PIL import Image, ImageFilter

        predictor = self._get_predictor()
        with Image.open(image_path) as source:
            rgb = source.convert("RGB")
            width, height = rgb.size
            predictor.set_image(np.asarray(rgb))

        left, top, right, bottom = bbox_1000
        pixel_box = np.asarray(
            [
                left / 1000 * width,
                top / 1000 * height,
                right / 1000 * width,
                bottom / 1000 * height,
            ],
            dtype=np.float32,
        )
        masks, scores, _ = predictor.predict(box=pixel_box, multimask_output=True)
        best_index = max(range(len(scores)), key=lambda index: float(scores[index]))
        mask = Image.fromarray((masks[best_index].astype("uint8") * 255), mode="L")
        dilation = max(0, int(self.settings.sam2_mask_dilation_px))
        if dilation:
            kernel = dilation * 2 + 1
            mask = mask.filter(ImageFilter.MaxFilter(kernel))
        feather = max(0, int(self.settings.sam2_mask_feather_px))
        if feather:
            mask = mask.filter(ImageFilter.GaussianBlur(feather))
        destination.parent.mkdir(parents=True, exist_ok=True)
        mask.save(destination)
        return destination

    def _get_predictor(self):
        if self._predictor is None:
            from sam2.build_sam import build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor

            model = build_sam2(
                self.settings.sam2_model_config,
                str(Path(self.settings.sam2_checkpoint).expanduser()),
                device=self.settings.sam2_device,
            )
            self._predictor = SAM2ImagePredictor(model)
        return self._predictor


class UnavailableSegmenter:
    @property
    def available(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "none"

    def segment_box(self, image_path: Path, bbox_1000: Box1000, destination: Path) -> Path:
        raise RuntimeError("No segmentation backend is configured.")


def create_segmenter(settings: Settings) -> Segmenter:
    segmenter = Sam2BoxSegmenter(settings)
    return segmenter if segmenter.available else UnavailableSegmenter()
