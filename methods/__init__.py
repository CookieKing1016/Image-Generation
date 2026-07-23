"""Benchmark prompt-building methods."""

from methods.base import BenchmarkMethod, MethodResult
from methods.current_only import CurrentOnlyMethod
from methods.full_history import FullHistoryMethod
from methods.structured_memory import StructuredMemoryMethod


METHODS = {
    "current-only": CurrentOnlyMethod,
    "full-history": FullHistoryMethod,
    "pullprompt": FullHistoryMethod,
    "structured-memory": StructuredMemoryMethod,
}


def create_method(name: str, client=None) -> BenchmarkMethod:
    try:
        method_cls = METHODS[name]
    except KeyError as exc:
        known = ", ".join(sorted(METHODS))
        raise ValueError(f"Unknown method '{name}'. Known methods: {known}") from exc
    return method_cls(client=client)
