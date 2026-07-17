import asyncio

from aiogram.exceptions import TelegramAPIError

from src.adapters.publishers.telegram import TelegramTextPublisher
from src.domain.ports.text_publisher import TextPublisherPort


class _Bot:
    def __init__(self, error=None):
        self.error = error
        self.call = None

    async def send_message(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return type("Message", (), {"message_id": 42})()


def test_telegram_publisher_sends_one_text_post():
    bot = _Bot()
    publisher = TelegramTextPublisher(bot, "@data_center_channel")

    result = asyncio.run(publisher.publish("post"))

    assert isinstance(publisher, TextPublisherPort)
    assert bot.call == {"chat_id": "@data_center_channel", "text": "post"}
    assert result.success is True
    assert result.external_id == "42"


def test_telegram_publisher_returns_safe_failure():
    error = TelegramAPIError(method=object(), message="token SECRET rejected")
    result = asyncio.run(TelegramTextPublisher(_Bot(error), "-1001").publish("post"))

    assert result.success is False
    assert "SECRET" not in (result.detail or "")
