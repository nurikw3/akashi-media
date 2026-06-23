"""In-memory PostRepository — the Phase 1 binding.

Non-durable by design (Scope Cut: no DB / no history). Implements the
PostRepository port so Phase 2 can swap in a real database adapter without
touching domain or application code.
"""

from __future__ import annotations

from src.domain.models import PublishResult


class InMemoryPostRepository:
    """Holds publish outcomes for the process lifetime only."""

    def __init__(self) -> None:
        self._results: list[PublishResult] = []

    def record(self, result: PublishResult) -> None:
        self._results.append(result)

    def all(self) -> list[PublishResult]:
        # Return a copy so callers cannot mutate internal state.
        return list(self._results)
