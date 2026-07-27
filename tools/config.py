"""Configuration loading without requiring python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


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
    aimlapi_key: str = ""
    aimlapi_base_url: str = "https://api.aimlapi.com/v1"
    llm_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    vlm_model: str = "Qwen/Qwen3-VL-32B-Instruct"
    image_model: str = "Kwai-Kolors/Kolors"
    image_fallback_models: List[str] = None
    image_edit_model: str = "Qwen/Qwen-Image-Edit-2509"
    image_inpaint_model: str = ""
    image_inpaint_provider: str = "siliconflow"
    segmentation_backend: str = "auto"
    sam2_checkpoint: str = ""
    sam2_model_config: str = ""
    sam2_device: str = "cpu"
    sam2_mask_dilation_px: int = 8
    sam2_mask_feather_px: int = 4
    image_size: str = "1024x1024"
    num_inference_steps: int = 20
    guidance_scale: float = 7.5
    timeout_seconds: int = 180
    vlm_max_retries: int = 2
    vlm_retry_delay_seconds: float = 1.0
    evaluation_mode: str = "interactive"
    refinement_max_attempts: int = 2
    refinement_score_threshold: float = 0.9
    residual_auto_retry: bool = True

    def __post_init__(self) -> None:
        if self.image_fallback_models is None:
            self.image_fallback_models = ["black-forest-labs/FLUX.1-schnell"]

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        return cls(
            api_key=os.getenv("SILICONFLOW_API_KEY", ""),
            base_url=os.getenv("SILICONFLOW_BASE_URL", cls.base_url),
            aimlapi_key=os.getenv("AIMLAPI_API_KEY", ""),
            aimlapi_base_url=os.getenv("AIMLAPI_BASE_URL", cls.aimlapi_base_url),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model),
            vlm_model=os.getenv("VLM_MODEL", cls.vlm_model),
            image_model=os.getenv("IMAGE_MODEL", cls.image_model),
            image_fallback_models=_env_csv("IMAGE_FALLBACK_MODELS", "black-forest-labs/FLUX.1-schnell"),
            image_edit_model=os.getenv("IMAGE_EDIT_MODEL", cls.image_edit_model),
            image_inpaint_model=os.getenv("IMAGE_INPAINT_MODEL", ""),
            image_inpaint_provider=os.getenv(
                "IMAGE_INPAINT_PROVIDER",
                cls.image_inpaint_provider,
            ).strip().lower(),
            segmentation_backend=os.getenv("SEGMENTATION_BACKEND", cls.segmentation_backend).strip().lower(),
            sam2_checkpoint=os.getenv("SAM2_CHECKPOINT", ""),
            sam2_model_config=os.getenv("SAM2_MODEL_CONFIG", ""),
            sam2_device=os.getenv("SAM2_DEVICE", cls.sam2_device),
            sam2_mask_dilation_px=_env_int("SAM2_MASK_DILATION_PX", cls.sam2_mask_dilation_px),
            sam2_mask_feather_px=_env_int("SAM2_MASK_FEATHER_PX", cls.sam2_mask_feather_px),
            image_size=os.getenv("IMAGE_SIZE", cls.image_size),
            num_inference_steps=_env_int("IMAGE_NUM_INFERENCE_STEPS", cls.num_inference_steps),
            guidance_scale=_env_float("IMAGE_GUIDANCE_SCALE", cls.guidance_scale),
            timeout_seconds=_env_int("SILICONFLOW_TIMEOUT_SECONDS", cls.timeout_seconds),
            vlm_max_retries=_env_int("VLM_MAX_RETRIES", cls.vlm_max_retries),
            vlm_retry_delay_seconds=_env_float("VLM_RETRY_DELAY_SECONDS", cls.vlm_retry_delay_seconds),
            evaluation_mode=os.getenv("EVALUATION_MODE", cls.evaluation_mode).strip().lower(),
            refinement_max_attempts=_env_int("REFINEMENT_MAX_ATTEMPTS", cls.refinement_max_attempts),
            refinement_score_threshold=_env_float("REFINEMENT_SCORE_THRESHOLD", cls.refinement_score_threshold),
            residual_auto_retry=_env_bool("RESIDUAL_AUTO_RETRY", cls.residual_auto_retry),
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


def _env_csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
