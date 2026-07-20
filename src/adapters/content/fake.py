"""FakeContentAdapter — deterministic ContentAdapterPort for tests and for
running locally without an OPENAI_API_KEY.
"""

from __future__ import annotations

from typing import Callable

from src.domain.models import Channel, ContentTask


class FakeContentAdapter:
    """Echoes the source into a channel frame, or applies an injected transform."""

    def __init__(self, transform: Callable[[str, Channel], str] | None = None) -> None:
        self._transform = transform

    def adapt(self, source_text: str, target: Channel) -> str:
        if self._transform is not None:
            return self._transform(source_text, target)
        return f"[{target.value.title()}-ready] {source_text}"

    def generate(self, task: ContentTask, brief: str) -> str:
        return f"[{task.value}] {brief}"
