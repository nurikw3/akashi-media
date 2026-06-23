"""OpenAIContentAdapter tested against a stub client — no real network calls."""

import pytest

from src.adapters.content.openai_adapter import OpenAIContentAdapter
from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel


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


def test_adapt_sends_hidden_system_prompt_and_user_text():
    client = _StubClient(content="Деловой пост для LinkedIn.")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")

    result = adapter.adapt("Чиллим на запуске 🚀", Channel.LINKEDIN)

    assert result == "Деловой пост для LinkedIn."
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    roles = [m["role"] for m in kwargs["messages"]]
    assert roles == ["system", "user"]
    # The hidden system prompt must be non-trivial and not equal to the user text.
    assert len(kwargs["messages"][0]["content"]) > 20
    assert kwargs["messages"][1]["content"] == "Чиллим на запуске 🚀"


def test_adapt_wraps_client_errors():
    client = _StubClient(error=RuntimeError("rate limited"))
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.adapt("text", Channel.LINKEDIN)


def test_adapt_rejects_empty_completion():
    client = _StubClient(content="   ")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.adapt("text", Channel.LINKEDIN)


def test_adapt_unknown_channel_raises():
    client = _StubClient(content="x")
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError):
        adapter.adapt("text", Channel.INSTAGRAM)  # no business-repackage prompt for IG


def test_adapt_error_message_does_not_leak_sdk_detail():
    client = _StubClient(error=RuntimeError("Incorrect API key provided: sk-proj-SECRET"))
    adapter = OpenAIContentAdapter(client=client, model="gpt-4o-mini")
    with pytest.raises(ContentAdaptationError) as excinfo:
        adapter.adapt("text", Channel.LINKEDIN)
    assert "sk-proj-SECRET" not in str(excinfo.value)


def test_adapters_satisfy_content_adapter_port():
    from src.adapters.content.fake import FakeContentAdapter
    from src.domain.ports.content_adapter import ContentAdapterPort

    assert isinstance(FakeContentAdapter(), ContentAdapterPort)
    assert isinstance(OpenAIContentAdapter(client=_StubClient(), model="m"), ContentAdapterPort)
