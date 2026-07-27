"""Small SiliconFlow API client based on the Python standard library."""

from __future__ import annotations

import base64
import http.client
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, request

from tools.config import Settings


class SiliconFlowError(RuntimeError):
    """Raised when SiliconFlow cannot complete a request."""


class SiliconFlowClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model or self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        return self._post_json("/chat/completions", payload)

    def vision_completion(
        self,
        prompt: str,
        image_path: Path,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        image_url = self.image_to_data_url(image_path)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
                ],
            }
        ]
        return self.chat_completion(
            messages=messages,
            model=model or self.settings.vlm_model,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )

    def generate_image(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        selected_model = model or self.settings.image_model
        payload: Dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "image_size": self.settings.image_size,
        }
        # FLUX schnell uses a fixed four-step serving configuration.
        if "flux.1-schnell" not in selected_model.lower():
            payload.update(
                {
                    "batch_size": 1,
                    "num_inference_steps": self.settings.num_inference_steps,
                    "guidance_scale": self.settings.guidance_scale,
                }
            )
        return self._post_json("/images/generations", payload)

    def generate_image_with_fallback(self, prompt: str) -> tuple[Dict[str, Any], str, List[Dict[str, str]]]:
        """Try configured image models in order and retain failed attempts."""
        candidates = _dedupe_models([self.settings.image_model, *self.settings.image_fallback_models])
        errors: List[Dict[str, str]] = []
        last_error: Optional[Exception] = None
        for model in candidates:
            try:
                return self.generate_image(prompt, model=model), model, errors
            except SiliconFlowError as exc:
                last_error = exc
                errors.append({"model": model, "error": str(exc)})
                if not _is_model_failover_error(str(exc)):
                    raise
        if last_error is not None:
            raise last_error
        raise SiliconFlowError("No image generation model is configured.")

    def edit_image(self, prompt: str, image_path: Path, negative_prompt: str = "") -> Dict[str, Any]:
        """Run an instruction-based image edit using the previous turn image.

        SiliconFlow exposes image-to-image models through the same endpoint as
        text-to-image generation.  Qwen Image Edit accepts the source image as
        a data URL and does not accept ``image_size``.
        """
        if not self.settings.image_edit_model:
            raise SiliconFlowError("IMAGE_EDIT_MODEL is disabled.")
        payload: Dict[str, Any] = {
            "model": self.settings.image_edit_model,
            "prompt": prompt,
            "image": self.image_to_data_url(image_path),
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return self._post_json("/images/generations", payload)

    def inpaint_image(
        self,
        prompt: str,
        image_path: Path,
        mask_path: Path,
        negative_prompt: str = "",
    ) -> Dict[str, Any]:
        """Run native inpainting with the source image and editable-region mask."""
        if not self.settings.image_inpaint_model:
            raise SiliconFlowError("IMAGE_INPAINT_MODEL is disabled.")
        payload: Dict[str, Any] = {
            "model": self.settings.image_inpaint_model,
            "prompt": prompt,
            "image": self.image_to_data_url(image_path),
            "mask": self.image_to_data_url(mask_path),
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return self._post_json("/images/generations", payload)

    def download_file(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        req = request.Request(url, headers={"User-Agent": "Mem2Image/0.1"})
        try:
            with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                destination.write_bytes(response.read())
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise SiliconFlowError(f"Image download failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise SiliconFlowError(f"Image download failed: {exc}") from exc

    def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.settings.api_key:
            raise SiliconFlowError(
                "SILICONFLOW_API_KEY is missing. Add it to .env or paste it in the Streamlit sidebar."
            )

        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mem2Image/0.1",
            },
        )

        max_attempts = max(1, self.settings.vlm_max_retries + 1)
        for attempt in range(max_attempts):
            try:
                with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:1200]
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_attempts - 1:
                    model = payload.get("model", "<unknown model>")
                    raise SiliconFlowError(
                        f"SiliconFlow API failed for model '{model}' at '{path}' with HTTP {exc.code}: {body}"
                    ) from exc
                _sleep_before_retry(self.settings, attempt)
            except (error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
                if attempt >= max_attempts - 1:
                    raise SiliconFlowError(f"SiliconFlow API connection failed: {exc}") from exc
                _sleep_before_retry(self.settings, attempt)
            except json.JSONDecodeError as exc:
                raise SiliconFlowError("SiliconFlow returned a non-JSON response.") from exc

        raise SiliconFlowError("SiliconFlow request exhausted its retry budget.")

    @staticmethod
    def image_to_data_url(image_path: Path) -> str:
        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"


def first_message_text(response: Dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SiliconFlowError("Unexpected chat completion response shape.") from exc

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content)


def first_image_url(response: Dict[str, Any]) -> str:
    url = ""
    try:
        if response.get("images"):
            url = response["images"][0]["url"]
        elif response.get("data"):
            url = response["data"][0]["url"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SiliconFlowError("Unexpected image generation response shape.") from exc
    if not url:
        raise SiliconFlowError(
            "Image generation response did not include an image URL in images[] or data[]."
        )
    return str(url)


def _dedupe_models(models: List[str]) -> List[str]:
    result = []
    seen = set()
    for model in models:
        normalized = str(model).strip()
        if normalized and normalized.lower() not in seen:
            result.append(normalized)
            seen.add(normalized.lower())
    return result


def _is_model_failover_error(message: str) -> bool:
    return any(token in message for token in ("HTTP 400", "HTTP 404", "HTTP 500", "HTTP 503", "HTTP 504"))


def _sleep_before_retry(settings: Settings, attempt: int) -> None:
    time.sleep(max(0.0, settings.vlm_retry_delay_seconds) * (attempt + 1))
