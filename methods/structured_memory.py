"""Project method based on explicit Visual Intent Memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.intent_parser import IntentParser
from agents.memory_updater import MemoryUpdater
from agents.prompt_composer import PromptComposer
from core.schema import empty_memory, normalize_memory
from methods.base import BenchmarkMethod, MethodResult


class StructuredMemoryMethod(BenchmarkMethod):
    name = "structured-memory"

    def __init__(self, client=None):
        super().__init__(client=client)
        if client is None:
            self.intent_parser = None
        else:
            self.intent_parser = IntentParser(client)
        self.memory_updater = MemoryUpdater()
        self.prompt_composer = PromptComposer()

    def initial_state(self) -> Dict[str, Any]:
        return empty_memory()

    def build_turn(
        self,
        instruction: str,
        history: List[str],
        state: Optional[Dict[str, Any]] = None,
    ) -> MethodResult:
        if self.intent_parser is None:
            raise RuntimeError("structured-memory requires an LLM client.")

        memory = normalize_memory(state or empty_memory())
        delta = self.intent_parser.parse(instruction, memory)
        next_memory = self.memory_updater.update(memory, delta, instruction)
        prompt = self.prompt_composer.compose(next_memory)
        return MethodResult(
            positive_prompt=prompt.positive,
            negative_prompt=prompt.negative,
            state=next_memory,
            delta=delta,
            metadata={"uses_history": True, "memory_keys": list(next_memory.keys())},
        )
