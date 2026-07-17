"""OpenAI-compatible adapter that creates one Telegram post per news item."""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from src.domain.errors import DigestCompositionError
from src.domain.models import NewsItem

TELEGRAM_TEXT_LIMIT = 4_096

_SYSTEM_PROMPT = """Ты — новостной редактор русскоязычного IT-дайджеста об индустрии дата-центров.
На основе РОВНО одной конкретной новостной статьи создай самостоятельную новостную заметку.

Требования:
- используй только факты из переданного заголовка и описания, ничего не выдумывай;
- не копируй длинные фрагменты исходника дословно;
- первая строка — конкретный новостной заголовок о произошедшем событии;
- затем в 2–4 коротких абзацах объясни: что произошло, кто участвует, где это
  случилось, какие известны даты, мощности, суммы или другие цифры;
- закончи абзацем «Почему это важно» с последствиями для рынка или технологий;
- если конкретной детали нет в материале, просто не упоминай её;
- не описывай сам сайт, блог, рубрику, подкаст или издание и не советуй их читать;
- не используй фразы «в материале рассказывается», «источник сообщает» и подобные;
- добавь 3–5 релевантных хэштегов;
- пиши по-русски, ясно и профессионально, без кликбейта и воды;
- целевая длина — 900–1600 символов;
- не добавляй ссылку на источник — приложение добавит её само;
- не используй Markdown, символы ** и служебные заголовки;
- верни только готовый текст поста без пояснений.
"""


class OpenAIDigestComposer:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    async def compose(self, item: NewsItem) -> str:
        published = item.published_at or "не указана"
        source_payload = (
            f"Заголовок: {item.title}\n"
            f"Дата публикации: {published}\n"
            f"Описание материала: {item.summary}"
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": source_payload},
                ],
            )
            content = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001 - external SDK boundary
            raise DigestCompositionError("Digest composition request failed") from exc

        if not content or not content.strip():
            raise DigestCompositionError("Digest composer returned empty text")

        provenance = (
            f"\n\nИсточник: {self._source_name(item.url)}\n"
            f"Дата публикации: {self._format_date(item.published_at)}\n"
            f"Ссылка: {item.url}"
        )
        available = TELEGRAM_TEXT_LIMIT - len(provenance)
        body = self._strip_markdown(content)
        if len(body) > available:
            body = f"{body[: available - 1].rstrip()}…"
        return f"{body}{provenance}"

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Keep Telegram plain-text output clean even if the LLM ignores the prompt."""
        cleaned = text.strip()
        cleaned = re.sub(r"```(?:[A-Za-z0-9_+-]+)?", "", cleaned)
        cleaned = re.sub(r"\[([^\]]+)]\((https?://[^)]+)\)", r"\1 — \2", cleaned)
        cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", cleaned)
        cleaned = re.sub(r"(?m)^\s*[-*]\s+", "• ", cleaned)
        cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "")
        return cleaned.strip()

    @staticmethod
    def _source_name(url: str) -> str:
        host = (urlparse(url).hostname or "").removeprefix("www.").casefold()
        names = {
            "datacenterdynamics.com": "Data Center Dynamics",
            "datacenterfrontier.com": "Data Center Frontier",
            "blog.equinix.com": "Equinix Blog",
            "newsroom.equinix.com": "Equinix Newsroom",
        }
        return names.get(host, host or "неизвестный источник")

    @staticmethod
    def _format_date(value: str | None) -> str:
        if not value:
            return "не указана"
        parsed: datetime | None = None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return parsed.strftime("%d.%m.%Y")
