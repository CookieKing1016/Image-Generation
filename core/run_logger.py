"""Run artifact logging for reproducible first-stage demos."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.schema import json_dumps


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "outputs" / "runs"


def make_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class RunLogger:
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or make_run_id()
        self.run_dir = RUNS_ROOT / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def turn_dir(self, turn_index: int) -> Path:
        path = self.run_dir / f"turn_{turn_index:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_dumps(data), encoding="utf-8")

    def save_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def save_turn_artifacts(
        self,
        turn_index: int,
        instruction: str,
        delta: Dict[str, Any],
        memory: Dict[str, Any],
        prompt_positive: str,
        prompt_negative: str,
        checklist: Any,
        evaluation: Any,
        image_path: Path,
        api_summary: Dict[str, Any],
    ) -> None:
        directory = self.turn_dir(turn_index)
        self.save_json(directory / "delta.json", delta)
        self.save_json(directory / "memory.json", memory)
        self.save_text(
            directory / "prompt.txt",
            f"POSITIVE PROMPT\n{prompt_positive}\n\nNEGATIVE PROMPT\n{prompt_negative}\n",
        )
        self.save_json(directory / "checklist.json", checklist)
        self.save_json(directory / "evaluation.json", evaluation)
        self.save_json(directory / "api_responses.json", api_summary)
        self.save_json(
            directory / "turn_log.json",
            {
                "turn": turn_index,
                "instruction": instruction,
                "image_path": str(image_path.relative_to(ROOT)),
                "memory_path": str((directory / "memory.json").relative_to(ROOT)),
                "prompt_path": str((directory / "prompt.txt").relative_to(ROOT)),
                "checklist_path": str((directory / "checklist.json").relative_to(ROOT)),
                "evaluation_path": str((directory / "evaluation.json").relative_to(ROOT)),
            },
        )

    def save_error(self, turn_index: int, stage: str, error: Exception) -> None:
        self.save_json(
            self.turn_dir(turn_index) / "error.json",
            {
                "turn": turn_index,
                "stage": stage,
                "error_type": type(error).__name__,
                "message": str(error),
            },
        )


def summarize_api_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Keep logs useful without storing large payloads or credentials."""
    summary: Dict[str, Any] = {}
    for key in ("id", "object", "created", "model", "seed", "timings", "usage"):
        if key in response:
            summary[key] = response[key]
    if "images" in response:
        summary["images"] = response["images"]
    if "choices" in response:
        summary["choices_count"] = len(response.get("choices", []))
    return summary

