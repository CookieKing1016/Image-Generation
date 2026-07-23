"""Baseline that concatenates all user instructions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from methods.base import DEFAULT_NEGATIVE_PROMPT, BenchmarkMethod, MethodResult


class FullHistoryMethod(BenchmarkMethod):
    name = "full-history"

    def build_turn(
        self,
        instruction: str,
        history: List[str],
        state: Optional[Dict[str, Any]] = None,
    ) -> MethodResult:
        all_turns = list(history) + [instruction]
        numbered = " ".join(f"Turn {idx}: {text}" for idx, text in enumerate(all_turns, 1))
        prompt = (
            "Use all instructions below as the accumulated visual intent. "
            f"{numbered} "
            "Resolve explicit replacements in later turns, preserve earlier details unless changed, "
            "and create one coherent high-quality image."
        )
        return MethodResult(
            positive_prompt=prompt,
            negative_prompt=DEFAULT_NEGATIVE_PROMPT,
            state={"history": all_turns},
            metadata={"uses_history": True, "history_turns": len(all_turns)},
        )
