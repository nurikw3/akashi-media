"""Command for the named workflows in the AKASHI content system."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import ContentAdaptationError
from src.domain.models import ContentTask
from src.domain.ports.content_adapter import ContentAdapterPort

MAX_BRIEF_CHARS = 8_000


@dataclass(frozen=True, slots=True)
class GenerateAkashiContentCommand:
    content_adapter: ContentAdapterPort

    def execute(self, task: ContentTask, brief: str) -> str:
        clean_brief = brief.strip()
        if not clean_brief:
            raise ContentAdaptationError("Content brief is empty")
        if len(clean_brief) > MAX_BRIEF_CHARS:
            raise ContentAdaptationError(f"Content brief exceeds {MAX_BRIEF_CHARS} characters")
        return self.content_adapter.generate(task, clean_brief)
