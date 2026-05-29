"""Small SiliconFlow API client based on the Python standard library."""

from __future__ import annotations

import base64
import json
import mimetypes
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

    def generate_image(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "image_size": self.settings.image_size,
            "batch_size": 1,
            "num_inference_steps": self.settings.num_inference_steps,
            "guidance_scale": self.settings.guidance_scale,
        }
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

        try:
            with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1200]
            model = payload.get("model", "<unknown model>")
            raise SiliconFlowError(
                f"SiliconFlow API failed for model '{model}' at '{path}' with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise SiliconFlowError(f"SiliconFlow API request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SiliconFlowError("SiliconFlow returned a non-JSON response.") from exc

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
    try:
        url = response["images"][0]["url"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SiliconFlowError("Unexpected image generation response shape.") from exc
    if not url:
        raise SiliconFlowError("Image generation response did not include an image URL.")
    return str(url)
