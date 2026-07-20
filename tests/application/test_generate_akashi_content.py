import pytest

from src.adapters.content.fake import FakeContentAdapter
from src.application.commands.generate_akashi_content import (
    MAX_BRIEF_CHARS,
    GenerateAkashiContentCommand,
)
from src.domain.errors import ContentAdaptationError
from src.domain.models import ContentTask


def test_generate_delegates_named_workflow_to_content_adapter():
    command = GenerateAkashiContentCommand(FakeContentAdapter())
    assert command.execute(ContentTask.GENERATE_IDEAS, "Фокус: AI") == "[generate_ideas] Фокус: AI"


@pytest.mark.parametrize("brief", ["   ", "x" * (MAX_BRIEF_CHARS + 1)])
def test_generate_rejects_empty_or_oversized_briefs(brief):
    with pytest.raises(ContentAdaptationError):
        GenerateAkashiContentCommand(FakeContentAdapter()).execute(ContentTask.CREATE_POST, brief)
