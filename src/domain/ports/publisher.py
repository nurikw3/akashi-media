"""PublisherPort — Strategy interface for publishing to a social channel.

Adapters (Instagram, LinkedIn, fake) implement this Protocol in src/adapters/.
The domain depends only on this abstraction, never on a concrete SDK.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.models import Channel, MediaFile, PublishResult


@runtime_checkable
class PublisherPort(Protocol):
    """Publishes text + one media file to a single channel, synchronously."""

    @property
    def channel(self) -> Channel:
        """The channel this publisher targets."""
        ...

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        """Publish immediately (Scope Cut: no scheduling).

        Return a PublishResult — success via PublishResult.ok, expected failures
        via PublishResult.failed (with a non-sensitive detail). Implementations
        should not raise for ordinary API failures.
        """
        ...
