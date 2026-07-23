"""Common interface for benchmark methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MethodResult:
    positive_prompt: str
    negative_prompt: str = ""
    state: Dict[str, Any] = field(default_factory=dict)
    delta: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def generation_prompt(self) -> str:
        if not self.negative_prompt:
            return self.positive_prompt
        return f"{self.positive_prompt}\nAvoid: {self.negative_prompt}"


class BenchmarkMethod:
    name = "base"

    def __init__(self, client=None):
        self.client = client

    def initial_state(self) -> Dict[str, Any]:
        return {}

    def build_turn(
        self,
        instruction: str,
        history: List[str],
        state: Optional[Dict[str, Any]] = None,
    ) -> MethodResult:
        raise NotImplementedError


DEFAULT_NEGATIVE_PROMPT = "low quality, blurry details, text artifacts, unintended extra subjects"
