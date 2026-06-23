"""PostRepository — Repository port.

Phase 1 is a transit gateway: history is NOT persisted (Scope Cut). The default
binding is an in-memory no-op-ish store so the contract exists for Phase 2 (DB)
without us building DB features now (YAGNI). Domain depends on this Protocol only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import PublishResult


@runtime_checkable
class PostRepository(Protocol):
    """Records publish outcomes. In Phase 1 this is best-effort, non-durable."""

    def record(self, result: PublishResult) -> None:
        """Store a publish outcome."""
        ...

    def all(self) -> list[PublishResult]:
        """Return all recorded outcomes (process lifetime only in Phase 1)."""
        ...
