import asyncio

from src.config import DigestContainer, DigestSettings
from src.domain.models import DigestPublishReport
from src.entrypoints.telegram.bot import DigestBotController, create_dispatcher


class _Command:
    def __init__(self, report=None):
        self.report = report or DigestPublishReport(2, 2, 2, 0)
        self.calls = []

    async def execute(self, limit):
        self.calls.append(limit)
        return self.report


class _Message:
    def __init__(self, chat_id):
        self.chat = type("Chat", (), {"id": chat_id})()
        self.answers = []

    async def answer(self, text):
        self.answers.append(text)


def _container(command, control_chat_id=123):
    settings = DigestSettings(
        telegram_bot_token="123:token",
        telegram_channel_id="-100456",
        telegram_control_chat_id=control_chat_id,
        tavily_api_key="tvly",
        openai_api_key="sk",
        post_limit=2,
    )
    return DigestContainer(settings=settings, bot=object(), command=command)


def test_authorized_one_runs_command_and_reports_result():
    command = _Command()
    message = _Message(123)
    controller = DigestBotController(_container(command))

    asyncio.run(controller.handle_trigger(message))

    assert command.calls == [2]
    assert "опубликовано 2 из 2" in message.answers[-1]


def test_unauthorized_chat_cannot_run_command():
    command = _Command()
    message = _Message(999)
    controller = DigestBotController(_container(command))

    asyncio.run(controller.handle_trigger(message))

    assert command.calls == []
    assert message.answers == ["Нет доступа к запуску публикации."]


def test_start_reveals_chat_id_only_for_configuration():
    message = _Message(777)
    controller = DigestBotController(_container(_Command(), control_chat_id=None))

    asyncio.run(controller.handle_start(message))

    assert "777" in message.answers[0]
    assert "TELEGRAM_CONTROL_CHAT_ID" in message.answers[0]


def test_dispatcher_is_constructed_with_routes():
    dispatcher = create_dispatcher(_container(_Command()))
    assert dispatcher.sub_routers
