import pytest

from src.adapters.content.fake import FakeContentAdapter
from src.application.commands.repackage_for_linkedin import RepackageForLinkedInCommand
from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel


def test_execute_returns_adapted_text():
    adapter = FakeContentAdapter(transform=lambda text, target: f"<{target.value}> {text}")
    command = RepackageForLinkedInCommand(content_adapter=adapter)

    result = command.execute("Запуск нового продукта 🚀")

    assert result == "<linkedin> Запуск нового продукта 🚀"


def test_execute_targets_linkedin_channel():
    seen = {}

    def capture(text, target):
        seen["target"] = target
        return "ok"

    command = RepackageForLinkedInCommand(content_adapter=FakeContentAdapter(transform=capture))
    command.execute("text")

    assert seen["target"] is Channel.LINKEDIN


def test_execute_strips_and_rejects_empty():
    command = RepackageForLinkedInCommand(content_adapter=FakeContentAdapter())
    with pytest.raises(ContentAdaptationError):
        command.execute("   ")


def test_execute_rejects_oversized_input():
    from src.application.commands.repackage_for_linkedin import MAX_SOURCE_CHARS

    command = RepackageForLinkedInCommand(content_adapter=FakeContentAdapter())
    with pytest.raises(ContentAdaptationError, match="exceeds"):
        command.execute("x" * (MAX_SOURCE_CHARS + 1))
