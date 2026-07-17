"""Port for immediate publication of text-only posts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import TextPublishResult


@runtime_checkable
class TextPublisherPort(Protocol):
    async def publish(self, text: str) -> TextPublishResult:
        """Publish one text post immediately."""
        ...
