"""aiogram long-polling entrypoint for manual data-center digest runs."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Dispatcher, F, Router

from src.config import DigestContainer, DigestSettings, build_digest_container
from src.domain.errors import DomainError

logger = logging.getLogger(__name__)


class DigestBotController:
    """Small transport controller; the publishing workflow stays in the command."""

    def __init__(self, container: DigestContainer) -> None:
        self._container = container
        self._run_lock = asyncio.Lock()

    async def handle_start(self, message: Any) -> None:
        control_chat_id = self._container.settings.telegram_control_chat_id
        if control_chat_id is None:
            text = (
                "Бот запущен. Ваш chat ID: "
                f"{message.chat.id}. Добавьте его в TELEGRAM_CONTROL_CHAT_ID "
                "и перезапустите бота."
            )
        elif message.chat.id == control_chat_id:
            text = "Бот готов. Отправьте 1, чтобы опубликовать IT-дайджест."
        else:
            text = "Бот настроен, но этот чат не имеет права запускать публикацию."
        await message.answer(text)

    async def handle_trigger(self, message: Any) -> None:
        if not self._is_authorized(message):
            await message.answer("Нет доступа к запуску публикации.")
            return
        if self._run_lock.locked():
            await message.answer("Дайджест уже формируется. Дождитесь завершения.")
            return

        async with self._run_lock:
            await message.answer("Ищу свежие материалы и готовлю публикации…")
            try:
                report = await self._container.command.execute(
                    limit=self._container.settings.post_limit
                )
            except DomainError:
                await message.answer(
                    "Не удалось подготовить дайджест. Проверьте ключи и попробуйте позже."
                )
                return
            except Exception:  # noqa: BLE001 - keep transport process alive
                logger.exception("Unexpected digest run failure")
                await message.answer("Внутренняя ошибка при подготовке дайджеста.")
                return

        if report.attempted == 0:
            await message.answer("Свежих подходящих материалов не найдено.")
            return
        await message.answer(
            f"Готово: опубликовано {report.published} из {report.attempted}. "
            f"Ошибок: {report.failed}."
        )

    async def handle_other(self, message: Any) -> None:
        if self._is_authorized(message):
            await message.answer("Для запуска дайджеста отправьте цифру 1.")

    def _is_authorized(self, message: Any) -> bool:
        control_chat_id = self._container.settings.telegram_control_chat_id
        return control_chat_id is not None and message.chat.id == control_chat_id


def create_dispatcher(container: DigestContainer) -> Dispatcher:
    controller = DigestBotController(container)
    router = Router(name="data_center_digest")
    router.message.register(controller.handle_start, F.text.in_({"/start", "/help"}))
    router.message.register(controller.handle_trigger, F.text == "1")
    router.message.register(controller.handle_other, F.chat.type == "private")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def run() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    settings = DigestSettings.from_env()
    container = build_digest_container(settings)
    dispatcher = create_dispatcher(container)

    try:
        await container.bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(
            container.bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await dispatcher.storage.close()
        await container.aclose()
        await container.bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
