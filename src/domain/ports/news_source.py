"""Port for retrieving current data-center industry materials."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import NewsItem


@runtime_checkable
class NewsSourcePort(Protocol):
    async def search(self, limit: int) -> tuple[NewsItem, ...]:
        """Return up to ``limit`` relevant, recent source items."""
        ...
