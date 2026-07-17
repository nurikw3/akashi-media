"""Text publisher backed by an injected aiogram Bot."""

from __future__ import annotations

from typing import Any

from aiogram.exceptions import TelegramAPIError

from src.domain.models import TextPublishResult


class TelegramTextPublisher:
    def __init__(self, bot: Any, channel_id: str) -> None:
        self._bot = bot
        self._channel_id = channel_id

    async def publish(self, text: str) -> TextPublishResult:
        try:
            message = await self._bot.send_message(chat_id=self._channel_id, text=text)
        except TelegramAPIError:
            return TextPublishResult.failed("Telegram publication failed")
        return TextPublishResult.ok(str(message.message_id))
