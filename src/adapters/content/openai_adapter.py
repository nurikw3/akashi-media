"""OpenAIContentAdapter — ContentAdapterPort backed by the OpenAI Chat API.

The hidden system prompt that turns casual Instagram copy into LinkedIn business
tone lives HERE, in the adapter — the domain never sees it. The OpenAI client is
injected so the adapter is unit-testable without network access.
"""

from __future__ import annotations

from typing import Any

from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel

# Hidden system prompts, keyed by target channel. Only channels we adapt FOR
# appear here; an unknown target is a programming error surfaced as an exception.
_SYSTEM_PROMPTS: dict[Channel, str] = {
    Channel.LINKEDIN: (
        "Ты — редактор деловых коммуникаций. Перепиши присланный текст поста в "
        "профессиональном деловом тоне для LinkedIn. Сохрани смысл и ключевые "
        "факты, убери сленг, чрезмерные эмодзи и просторечие. Структурируй: "
        "цепляющее первое предложение, 2–4 коротких абзаца, по необходимости — "
        "список и уместный призыв к действию. Добавь 3–5 релевантных хэштегов в "
        "конце. Отвечай только готовым текстом поста на языке оригинала, без "
        "пояснений и markdown-разметки."
    ),
}


class OpenAIContentAdapter:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def adapt(self, source_text: str, target: Channel) -> str:
        system_prompt = _SYSTEM_PROMPTS.get(target)
        if system_prompt is None:
            raise ContentAdaptationError(f"No adaptation prompt configured for {target.value}")

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": source_text},
                ],
            )
            content = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001 — wrap any SDK/transport failure
            # Never embed `exc` text in the message: OpenAI SDK errors can echo
            # request payloads or API-key fragments. The cause is chained for
            # server-side tracebacks only.
            raise ContentAdaptationError("LLM request failed") from exc

        if not content or not content.strip():
            raise ContentAdaptationError("LLM returned an empty completion")
        return content.strip()
