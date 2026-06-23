import pytest

from src.config import Settings


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
    assert settings.openai_model == "gpt-4o-mini"  # default
    assert settings.ig_token is None  # absent → None


@pytest.mark.parametrize("missing", ["APP_USERNAME", "APP_PASSWORD", "APP_SECRET_KEY"])
def test_from_env_raises_on_missing_required(missing):
    env = {"APP_USERNAME": "u", "APP_PASSWORD": "p", "APP_SECRET_KEY": "x" * 32}
    del env[missing]
    with pytest.raises(RuntimeError, match=missing):
        Settings.from_env(env)
