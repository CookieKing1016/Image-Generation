"""AI/ML API client for native image inpainting."""

from __future__ import annotations

import base64
import http.client
import io
import json
from pathlib import Path
from typing import Any, Dict
from urllib import error, request

from tools.config import Settings


class AIMLAPIError(RuntimeError):
    """Raised when AI/ML API cannot complete an image request."""


class AIMLAPIClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.aimlapi_base_url.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(
            self.settings.image_inpaint_provider == "aimlapi"
            and self.settings.aimlapi_key
            and self.settings.image_inpaint_model
        )

    def inpaint_image(
        self,
        prompt: str,
        image_path: Path,
        mask_path: Path,
        negative_prompt: str = "",
    ) -> Dict[str, Any]:
        if not self.settings.aimlapi_key:
            raise AIMLAPIError("AIMLAPI_API_KEY is missing.")
        if not self.settings.image_inpaint_model:
            raise AIMLAPIError("IMAGE_INPAINT_MODEL is disabled.")
        payload: Dict[str, Any] = {
            "model": self.settings.image_inpaint_model,
            "prompt": prompt,
            "image": _image_to_data_url(image_path),
            "mask": _binary_mask_to_data_url(mask_path),
            "response_format": "url",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return self._post_json("/images/generations", payload)

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.aimlapi_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mem2Image/0.1",
            },
        )
        try:
            with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1200]
            model = payload.get("model", "<unknown model>")
            raise AIMLAPIError(
                f"AI/ML API failed for model '{model}' at '{path}' "
                f"with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise AIMLAPIError(f"AI/ML API request failed: {exc}") from exc
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            raise AIMLAPIError(f"AI/ML API connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIMLAPIError("AI/ML API returned a non-JSON response.") from exc


def _image_to_data_url(image_path: Path) -> str:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _binary_mask_to_data_url(mask_path: Path) -> str:
    """Convert soft SAM2/local masks to the black-white mask FLUX Fill expects."""
    from PIL import Image

    with Image.open(mask_path) as mask:
        binary = mask.convert("L").point(lambda value: 255 if value >= 128 else 0)
        buffer = io.BytesIO()
        binary.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
