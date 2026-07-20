"""OpenAIContentAdapter — ContentAdapterPort backed by the OpenAI Chat API.

The hidden system prompt that turns casual Instagram copy into LinkedIn business
tone lives HERE, in the adapter — the domain never sees it. The OpenAI client is
injected so the adapter is unit-testable without network access.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.domain.errors import ContentAdaptationError
from src.adapters.content.akashi_prompts import system_prompt
from src.domain.models import Channel, ContentTask

logger = logging.getLogger(__name__)


def _plain_social_text(text: str) -> str:
    """Remove presentation-only Markdown from a model-generated social post."""
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    return text.replace("**", "").replace("__", "").replace("`", "").strip()


def _source_length(brief: str) -> int:
    lines = brief.strip().splitlines()
    if lines and lines[0].strip().casefold() in {
        "исходный текст:",
        "instagram-текст:",
        "текст instagram:",
    }:
        return len("\n".join(lines[1:]).strip())
    return len(brief.strip())


def _source_sentence_budget(brief: str) -> int:
    text = brief.strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    instagram_cta = ("листайте", "свайп", "смотрите слайды", "swipe", "carousel")
    meaningful = [
        sentence for sentence in sentences
        if sentence.strip() and not any(marker in sentence.casefold() for marker in instagram_cta)
    ]
    return max(1, len(meaningful))


def _limit_sentences(text: str, limit: int) -> str:
    sentences = [item for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item]
    return " ".join(sentences[:limit]).strip()


class OpenAIContentAdapter:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    def adapt(self, source_text: str, target: Channel) -> str:
        if target is not Channel.LINKEDIN:
            raise ContentAdaptationError(f"No adaptation prompt configured for {target.value}")
        return self.generate(ContentTask.INSTAGRAM_TO_LINKEDIN, source_text)

    def generate(self, task: ContentTask, brief: str) -> str:
        try:
            prompt = system_prompt(task)
            if task is ContentTask.INSTAGRAM_TO_LINKEDIN:
                prompt += (
                    f"\n\nЛимит каждой языковой версии: не более {_source_length(brief)} "
                    "символов. Закончи обе версии полным предложением; не обрывай "
                    "слова ради лимита."
                )
            request: dict[str, Any] = {
                "model": self._model,
                "temperature": 0.2 if task is ContentTask.INSTAGRAM_TO_LINKEDIN else 0.7,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": brief},
                ],
            }
            if task is ContentTask.INSTAGRAM_TO_LINKEDIN:
                request["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "linkedin_adaptation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "english": {"type": "string"},
                                "russian": {"type": "string"},
                            },
                            "required": ["english", "russian"],
                            "additionalProperties": False,
                        },
                    },
                }
            response = self._client.chat.completions.create(**request)
            content = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001 — wrap any SDK/transport failure
            # Never embed `exc` text in the message: OpenAI SDK errors can echo
            # request payloads or API-key fragments. The cause is chained for
            # server-side tracebacks only.
            logger.error(
                "OpenAI content request failed: error_type=%s status=%s code=%s request_id=%s model=%s cause_type=%s cause=%s",
                type(exc).__name__,
                getattr(exc, "status_code", None),
                getattr(exc, "code", None),
                getattr(exc, "request_id", None),
                self._model,
                type(exc.__cause__).__name__ if exc.__cause__ else None,
                str(exc.__cause__)[:300] if exc.__cause__ else None,
            )
            raise ContentAdaptationError("LLM request failed") from exc

        if not content or not content.strip():
            raise ContentAdaptationError("LLM returned an empty completion")
        if task is ContentTask.INSTAGRAM_TO_LINKEDIN:
            try:
                bilingual = json.loads(content)
                sentence_budget = _source_sentence_budget(brief)
                english = _limit_sentences(
                    _plain_social_text(bilingual["english"]), sentence_budget
                )
                russian = _limit_sentences(
                    _plain_social_text(bilingual["russian"]), sentence_budget
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ContentAdaptationError("LLM returned an invalid LinkedIn adaptation") from exc
            if not english or not russian:
                raise ContentAdaptationError("LLM returned an empty LinkedIn adaptation")
            content = f"{english}\n\n__________\n\n{russian}"
        return content.strip()
