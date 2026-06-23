"""PublisherFactory — selects a PublisherPort strategy by channel.

Factory pattern: the composition root builds the concrete publisher instances
and hands them to the factory; callers select one by Channel or by string.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.domain.errors import UnknownChannelError
from src.domain.models import Channel
from src.domain.ports.publisher import PublisherPort


class PublisherFactory:
    def __init__(self, publishers: Mapping[Channel, PublisherPort]) -> None:
        self._publishers = dict(publishers)

    def create(self, channel: Channel | str) -> PublisherPort:
        try:
            resolved = channel if isinstance(channel, Channel) else Channel(channel)
        except ValueError as exc:
            raise UnknownChannelError(f"Unknown channel: {channel!r}") from exc

        publisher = self._publishers.get(resolved)
        if publisher is None:
            raise UnknownChannelError(f"No publisher registered for channel: {resolved.value}")
        return publisher
