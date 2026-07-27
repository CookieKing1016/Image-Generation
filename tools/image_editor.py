"""Provider-neutral boundary for instruction-based image editing backends."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Protocol

from tools.aimlapi_client import AIMLAPIClient, AIMLAPIError
from tools.siliconflow_client import SiliconFlowClient, SiliconFlowError, first_image_url
from core.mask_utils import composite_masked_edit


@dataclass
class ImageEditResult:
    image_path: Path
    response: Dict[str, Any]
    candidate_path: Path | None = None
    backend: str = "reference_edit"


class ImageEditor(Protocol):
    @property
    def available(self) -> bool: ...

    def edit(self, image_path: Path, instruction: str, destination: Path, negative_prompt: str = "", mask_path: Path | None = None) -> ImageEditResult: ...


class SiliconFlowImageEditor:
    """Instruction-based image editing with the previous image as reference."""

    def __init__(
        self,
        client: SiliconFlowClient,
        aimlapi_client: AIMLAPIClient | None = None,
    ):
        self.client = client
        self.aimlapi_client = aimlapi_client

    @property
    def available(self) -> bool:
        if self.client.settings.image_inpaint_provider == "aimlapi":
            inpaint_available = bool(
                self.aimlapi_client and self.aimlapi_client.available
            )
        else:
            inpaint_available = bool(self.client.settings.image_inpaint_model)
        return bool(self.client.settings.image_edit_model or inpaint_available)

    def edit(self, image_path: Path, instruction: str, destination: Path, negative_prompt: str = "", mask_path: Path | None = None) -> ImageEditResult:
        native_error = ""
        if mask_path and mask_path.is_file() and self.client.settings.image_inpaint_model:
            try:
                if self.client.settings.image_inpaint_provider == "aimlapi":
                    if not self.aimlapi_client:
                        raise AIMLAPIError("AI/ML API inpainting client is unavailable.")
                    response = self.aimlapi_client.inpaint_image(
                        instruction,
                        image_path,
                        mask_path,
                        negative_prompt=negative_prompt,
                    )
                    backend = "aimlapi_flux_fill"
                else:
                    response = self.client.inpaint_image(
                        instruction,
                        image_path,
                        mask_path,
                        negative_prompt=negative_prompt,
                    )
                    backend = "native_inpainting"
                self.client.download_file(first_image_url(response), destination)
                return ImageEditResult(
                    image_path=destination,
                    response=response,
                    backend=backend,
                )
            except (AIMLAPIError, SiliconFlowError) as exc:
                native_error = str(exc)
                if not self.client.settings.image_edit_model:
                    raise

        response = self.client.edit_image(instruction, image_path, negative_prompt=negative_prompt)
        if native_error:
            response = {
                **response,
                "_mem2image": {
                    "fallback_from": "native_inpainting",
                    "error": native_error,
                },
            }
        candidate_path = destination.with_name("candidate_image.png")
        self.client.download_file(first_image_url(response), candidate_path)
        if mask_path and mask_path.is_file():
            composite_masked_edit(image_path, candidate_path, mask_path, destination)
            backend = "reference_edit_local_composite"
        else:
            candidate_path.replace(destination)
            candidate_path = None
            backend = "reference_edit"
        return ImageEditResult(
            image_path=destination,
            response=response,
            candidate_path=candidate_path,
            backend=backend,
        )


class UnavailableImageEditor:
    @property
    def available(self) -> bool:
        return False

    def edit(self, image_path: Path, instruction: str, destination: Path, negative_prompt: str = "", mask_path: Path | None = None) -> ImageEditResult:
        raise RuntimeError("No image editing backend is configured.")
