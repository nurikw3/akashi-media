"""ContentAdapterPort — Strategy interface for AI text adaptation.

The OpenAI adapter implements this in src/adapters/. The hidden system prompt
that rewrites Instagram copy into LinkedIn business tone lives in the adapter,
not here — the domain only knows "adapt this text for that channel".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import Channel


@runtime_checkable
class ContentAdapterPort(Protocol):
    """Rewrites source text to fit a target channel's tone/format."""

    def adapt(self, source_text: str, target: Channel) -> str:
        """Return adapted text. Raise ContentAdaptationError on failure."""
        ...
