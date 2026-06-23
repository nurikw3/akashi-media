"""Command: repackage source copy into LinkedIn business tone via the AI port.

One use-case = one class (Command pattern). Depends only on the
ContentAdapterPort abstraction, never on a concrete LLM SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel
from src.domain.ports.content_adapter import ContentAdapterPort

# Caps the text forwarded to the paid LLM API — bounds per-request cost and is
# well above any realistic social caption (IG ~2200 / LinkedIn ~3000 chars).
MAX_SOURCE_CHARS = 5_000


@dataclass(frozen=True, slots=True)
class RepackageForLinkedInCommand:
    content_adapter: ContentAdapterPort

    def execute(self, source_text: str) -> str:
        text = source_text.strip()
        if not text:
            raise ContentAdaptationError("Source text is empty")
        if len(text) > MAX_SOURCE_CHARS:
            raise ContentAdaptationError(
                f"Source text exceeds {MAX_SOURCE_CHARS} characters"
            )
        return self.content_adapter.adapt(text, Channel.LINKEDIN)
