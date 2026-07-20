"""OpenAIContentAdapter tested against a stub client — no real network calls."""

import pytest

from src.adapters.content.openai_adapter import OpenAIContentAdapter
from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel, ContentTask


class _StubMessage:
    def __init__(self, content):
        self.content = content


class _StubChoice:
    def __init__(self, content):
        self.message = _StubMessage(content)


class _StubResponse:
    def __init__(self, content):
        self.choices = [_StubChoice(content)]


class _StubCompletions:
    def __init__(self, content=None, error=None):
        self._content = content
        self._error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error:
            raise self._error
        return _StubResponse(self._content)


class _StubClient:
    def __init__(self, content=None, error=None):
        self.chat = type("Chat", (), {"completions": _StubCompletions(content, error)})()


def test_adapt_returns_only_plain_linkedin_post():
    client = _StubClient(
        content='{"english":"**AKASHI business copy.**","russian":"**Деловой текст AKASHI.**"}'
    )
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")

    result = adapter.adapt("Разговорный Instagram-текст 🚀", Channel.LINKEDIN)

    assert result == "AKASHI business copy.\n\n__________\n\nДеловой текст AKASHI."
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.2
    assert kwargs["response_format"]["type"] == "json_schema"
    assert "Лимит каждой языковой версии" in kwargs["messages"][0]["content"]
    assert kwargs["messages"][1]["content"] == "Разговорный Instagram-текст 🚀"


def test_generate_uses_the_selected_akashi_workflow():
    client = _StubClient(content="Идея: резервирование")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")

    result = adapter.generate(ContentTask.GENERATE_IDEAS, "Период: август")

    assert result == "Идея: резервирование"
    prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
    assert "AKASHI" in prompt
    assert "оценка X/14" in prompt
    assert client.chat.completions.last_kwargs["messages"][1]["content"] == "Период: август"


def test_instagram_to_linkedin_forbids_meta_sections_and_markdown():
    client = _StubClient(
        content='{"english":"Ready copy.","russian":"Готовый текст без служебных секций."}'
    )
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")

    result = adapter.generate(
        ContentTask.INSTAGRAM_TO_LINKEDIN,
        "Исходная Instagram-публикация.",
    )

    assert result == "Ready copy.\n\n__________\n\nГотовый текст без служебных секций."
    prompt = client.chat.completions.last_kwargs["messages"][0]["content"]
    assert "сдержанном стиле AKASHI" in prompt
    assert "две равнозначные версии" in prompt
    assert "не длиннее исходника" in prompt
    assert "запрещены Markdown" in prompt
    assert "Core" in prompt


def test_instagram_to_linkedin_does_not_expand_one_source_thesis():
    client = _StubClient(
        content=(
            '{"english":"First adapted sentence. Redundant expansion.",'
            '"russian":"Первое предложение. Лишнее повторение."}'
        )
    )
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")

    result = adapter.generate(
        ContentTask.INSTAGRAM_TO_LINKEDIN,
        "Один исходный тезис. Листайте карусель, чтобы узнать больше.",
    )

    assert result == "First adapted sentence.\n\n__________\n\nПервое предложение."


def test_generate_wraps_client_errors():
    client = _StubClient(error=RuntimeError("rate limited"))
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.generate(ContentTask.CREATE_POST, "text")


def test_generate_rejects_empty_completion():
    client = _StubClient(content="   ")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.generate(ContentTask.CREATE_POST, "text")


def test_adapt_unknown_channel_raises():
    client = _StubClient(content="x")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.adapt("text", Channel.INSTAGRAM)  # no business-repackage prompt for IG


def test_generate_error_message_does_not_leak_sdk_detail():
    client = _StubClient(error=RuntimeError("Incorrect API key provided: sk-proj-SECRET"))
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError) as excinfo:
        adapter.generate(ContentTask.CREATE_POST, "text")
    assert "sk-proj-SECRET" not in str(excinfo.value)


def test_adapters_satisfy_content_adapter_port():
    from src.adapters.content.fake import FakeContentAdapter
    from src.domain.ports.content_adapter import ContentAdapterPort

    assert isinstance(FakeContentAdapter(), ContentAdapterPort)
    assert isinstance(OpenAIContentAdapter(client=_StubClient(), model="m"), ContentAdapterPort)
