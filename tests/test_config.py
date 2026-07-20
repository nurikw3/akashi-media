from dataclasses import replace

import pytest

from src.adapters.publishers.buffer import BufferPublisher
from src.adapters.publishers.instagram import InstagramGraphPublisher
from src.adapters.publishers.linkedin import LinkedInPublisher
from src.config import DigestSettings, Settings, build_container
from src.domain.models import Channel


def test_from_env_reads_required_and_optional():
    env = {
        "APP_USERNAME": "u",
        "APP_PASSWORD": "p",
        "APP_SECRET_KEY": "x" * 32,
        "OPENAI_API_KEY": "sk-test",
    }
    settings = Settings.from_env(env)
    assert settings.username == "u"
    assert settings.openai_api_key == "sk-test"
    assert settings.openai_model == "openai/gpt-oss-120b"  # requested default
    assert settings.openai_base_url == "https://api.groq.com/openai/v1"
    assert settings.ig_token is None  # absent → None
    assert settings.database_url is None
    assert settings.buffer_api_key is None
    assert settings.buffer_instagram_channel_id is None


def test_from_env_reads_buffer_channel_ids_and_normalizes_blanks():
    settings = Settings.from_env(
        {
            "APP_USERNAME": "u",
            "APP_PASSWORD": "p",
            "APP_SECRET_KEY": "x" * 32,
            "BUFFER_API_KEY": " key ",
            "BUFFER_LINKEDIN_CHANNEL_ID": " linkedin-id ",
            "BUFFER_INSTAGRAM_CHANNEL_ID": " instagram-id ",
        }
    )

    assert settings.buffer_api_key == "key"
    assert settings.buffer_linkedin_channel_id == "linkedin-id"
    assert settings.buffer_instagram_channel_id == "instagram-id"


@pytest.mark.parametrize("missing", ["APP_USERNAME", "APP_PASSWORD", "APP_SECRET_KEY"])
def test_from_env_raises_on_missing_required(missing):
    env = {"APP_USERNAME": "u", "APP_PASSWORD": "p", "APP_SECRET_KEY": "x" * 32}
    del env[missing]
    with pytest.raises(RuntimeError, match=missing):
        Settings.from_env(env)


def test_digest_settings_read_required_values_and_limits():
    settings = DigestSettings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "123:token",
            "TELEGRAM_CHANNEL_ID": "-100123",
            "TELEGRAM_CONTROL_CHAT_ID": "42",
            "TAVILY_API_KEY": "tvly",
            "OPENAI_API_KEY": "sk",
            "DIGEST_POST_LIMIT": "2",
        }
    )

    assert settings.telegram_control_chat_id == 42
    assert settings.post_limit == 2
    assert settings.openai_model == "openai/gpt-oss-120b"
    assert settings.openai_base_url == "https://api.groq.com/openai/v1"
    assert settings.database_url is None


@pytest.mark.parametrize("value", ["0", "6", "not-a-number"])
def test_digest_settings_reject_invalid_post_limit(value):
    env = {
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_CHANNEL_ID": "-100123",
        "TAVILY_API_KEY": "tvly",
        "OPENAI_API_KEY": "sk",
        "DIGEST_POST_LIMIT": value,
    }
    with pytest.raises(RuntimeError, match="DIGEST_POST_LIMIT"):
        DigestSettings.from_env(env)


class _HttpClient:
    def close(self):
        pass


def test_buffer_publishers_have_priority_for_each_configured_channel(settings, monkeypatch):
    monkeypatch.setattr("src.config._http_client", _HttpClient)
    configured = replace(
        settings,
        public_base_url="https://akashi.example",
        buffer_api_key="buffer-key",
        buffer_instagram_channel_id="buffer-instagram",
        buffer_linkedin_channel_id="buffer-linkedin",
        ig_token="ig-token",
        ig_user_id="ig-user",
        li_token="li-token",
        li_author_urn="urn:li:person:1",
    )

    container = build_container(configured)

    instagram = container.publisher_factory.create(Channel.INSTAGRAM)
    linkedin = container.publisher_factory.create(Channel.LINKEDIN)
    assert isinstance(instagram, BufferPublisher)
    assert isinstance(linkedin, BufferPublisher)
    assert instagram.channel is Channel.INSTAGRAM
    assert linkedin.channel is Channel.LINKEDIN
    assert len(container.closeables) == 2


def test_direct_publishers_remain_fallbacks_without_buffer_channel_ids(settings, monkeypatch):
    monkeypatch.setattr("src.config._http_client", _HttpClient)
    configured = replace(
        settings,
        public_base_url="https://akashi.example",
        buffer_api_key="buffer-key",
        ig_token="ig-token",
        ig_user_id="ig-user",
        li_token="li-token",
        li_author_urn="urn:li:person:1",
    )

    container = build_container(configured)

    assert isinstance(
        container.publisher_factory.create(Channel.INSTAGRAM), InstagramGraphPublisher
    )
    assert isinstance(container.publisher_factory.create(Channel.LINKEDIN), LinkedInPublisher)
