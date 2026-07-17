import pytest

from src.config import DigestSettings, Settings


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
