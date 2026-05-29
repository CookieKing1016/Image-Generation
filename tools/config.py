"""Configuration loading without requiring python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Optional[Path] = None) -> Dict[str, str]:
    env_path = path or ROOT / ".env"
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
            os.environ.setdefault(key, value)
    return values


@dataclass
class Settings:
    api_key: str = ""
    base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    vlm_model: str = "Qwen/Qwen3-VL-32B-Instruct"
    image_model: str = "Kwai-Kolors/Kolors"
    image_size: str = "1024x1024"
    num_inference_steps: int = 20
    guidance_scale: float = 7.5
    timeout_seconds: int = 180

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        return cls(
            api_key=os.getenv("SILICONFLOW_API_KEY", ""),
            base_url=os.getenv("SILICONFLOW_BASE_URL", cls.base_url),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            vlm_model=os.getenv("VLM_MODEL", cls.vlm_model),
            image_model=os.getenv("IMAGE_MODEL", cls.image_model),
            image_size=os.getenv("IMAGE_SIZE", cls.image_size),
            num_inference_steps=_env_int("IMAGE_NUM_INFERENCE_STEPS", cls.num_inference_steps),
            guidance_scale=_env_float("IMAGE_GUIDANCE_SCALE", cls.guidance_scale),
            timeout_seconds=_env_int("SILICONFLOW_TIMEOUT_SECONDS", cls.timeout_seconds),
        )


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
