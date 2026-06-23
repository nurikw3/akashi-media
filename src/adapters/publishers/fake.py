"""FakePublisher — deterministic PublisherPort for tests and token-less runs.

This is the DEFAULT Phase-1 binding for any channel without live credentials:
it proves the upload → command → factory → result flow end to end without
calling a real social API.
"""

from __future__ import annotations

from src.domain.models import Channel, MediaFile, PublishResult


class FakePublisher:
    def __init__(self, channel: Channel, succeed: bool = True) -> None:
        self._channel = channel
        self._succeed = succeed
        self.published: list[tuple[str, MediaFile]] = []

    @property
    def channel(self) -> Channel:
        return self._channel

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        self.published.append((text, media))
        if self._succeed:
            return PublishResult.ok(
                self._channel,
                external_id=f"fake-{self._channel.value}-1",
                detail="Опубликовано (тестовый адаптер)",
            )
        return PublishResult.failed(self._channel, detail="Тестовая ошибка публикации")
