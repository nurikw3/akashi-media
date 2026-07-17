import asyncio

import pytest

from src.adapters.content.openai_digest_composer import (
    TELEGRAM_TEXT_LIMIT,
    OpenAIDigestComposer,
)
from src.domain.errors import DigestCompositionError
from src.domain.models import NewsItem
from src.domain.ports.digest_composer import DigestComposerPort


class _Message:
    def __init__(self, content):
        self.content = content


class _Completions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        choice = type("Choice", (), {"message": _Message(self.content)})()
        return type("Response", (), {"choices": [choice]})()


class _Client:
    def __init__(self, content=None, error=None):
        completions = _Completions(content, error)
        self.chat = type("Chat", (), {"completions": completions})()


def _item():
    return NewsItem(
        title="Liquid cooling update",
        url="https://example.com/cooling",
        summary="Operators are testing a new liquid cooling design.",
        published_at="2026-07-14",
    )


def test_composer_uses_requested_model_and_appends_trusted_source_url():
    client = _Client("Готовый самостоятельный пост. #датацентры")
    composer = OpenAIDigestComposer(client, "openai/gpt-oss-120b")

    text = asyncio.run(composer.compose(_item()))

    assert isinstance(composer, DigestComposerPort)
    assert client.chat.completions.kwargs["model"] == "openai/gpt-oss-120b"
    assert "Liquid cooling update" in client.chat.completions.kwargs["messages"][1]["content"]
    assert "Источник: example.com" in text
    assert "Дата публикации: 14.07.2026" in text
    assert text.endswith("Ссылка: https://example.com/cooling")


def test_composer_enforces_telegram_limit():
    text = asyncio.run(OpenAIDigestComposer(_Client("x" * 5000), "m").compose(_item()))
    assert len(text) == TELEGRAM_TEXT_LIMIT


def test_composer_removes_markdown_that_would_render_as_raw_symbols():
    content = "**Заголовок**\n\n### Почему это важно\n* Первый пункт\n`код`"
    text = asyncio.run(OpenAIDigestComposer(_Client(content), "m").compose(_item()))

    assert "**" not in text
    assert "###" not in text
    assert "`" not in text
    assert "• Первый пункт" in text


def test_composer_wraps_errors_and_rejects_empty_content():
    with pytest.raises(DigestCompositionError) as excinfo:
        asyncio.run(OpenAIDigestComposer(_Client(error=RuntimeError("sk-secret")), "m").compose(_item()))
    assert "sk-secret" not in str(excinfo.value)

    with pytest.raises(DigestCompositionError):
        asyncio.run(OpenAIDigestComposer(_Client(" "), "m").compose(_item()))
