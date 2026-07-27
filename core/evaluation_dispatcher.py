"""Background evaluation dispatch for non-blocking interactive edits."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List

from agents.evaluator import ChecklistEvaluator


class EvaluationDispatcher:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mem2image-eval")

    def submit(
        self,
        evaluator: ChecklistEvaluator,
        image_path: Path,
        checklist: List[Dict[str, Any]],
        memory: Dict[str, Any],
        prompt: str,
        on_success: Callable[[Dict[str, Any]], None],
        on_error: Callable[[Exception], None],
    ) -> Future:
        future = self._executor.submit(evaluator.evaluate, image_path, checklist, memory, prompt)

        def _persist_result(completed: Future) -> None:
            try:
                on_success(completed.result())
            except Exception as exc:
                on_error(exc)

        future.add_done_callback(_persist_result)
        return future
