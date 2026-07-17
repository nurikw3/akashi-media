"""Port for turning one source item into one original Telegram post."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import NewsItem


@runtime_checkable
class DigestComposerPort(Protocol):
    async def compose(self, item: NewsItem) -> str:
        """Create one publish-ready post from one source item."""
        ...
