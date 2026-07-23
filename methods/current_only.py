"""Baseline that prompts only with the current turn."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from methods.base import DEFAULT_NEGATIVE_PROMPT, BenchmarkMethod, MethodResult


class CurrentOnlyMethod(BenchmarkMethod):
    name = "current-only"

    def build_turn(
        self,
        instruction: str,
        history: List[str],
        state: Optional[Dict[str, Any]] = None,
    ) -> MethodResult:
        prompt = (
            f"Current user request: {instruction} "
            "Create a coherent, high-quality image with clear composition and visible requested details."
        )
        return MethodResult(
            positive_prompt=prompt,
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            state={"history": list(history) + [instruction]},
            metadata={"uses_history": False},
        )
