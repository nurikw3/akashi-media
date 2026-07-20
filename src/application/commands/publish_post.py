"""Command: publish a post (text + media) through a channel publisher.

One use-case. Depends only on domain ports (PublisherPort, PostRepository) —
the channel strategy is selected by the PublisherFactory in the entrypoint and
injected here, keeping the application layer free of adapter imports. Shared by
the Instagram (S2) and LinkedIn (S3) slices.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.models import MediaFile, PublishResult
from src.domain.ports.post_repository import PostRepository
from src.domain.ports.publisher import PublisherPort


@dataclass(frozen=True, slots=True)
class PublishPostCommand:
    publisher: PublisherPort
    post_repository: PostRepository

    def execute(self, text: str, media: MediaFile | tuple[MediaFile, ...]) -> PublishResult:
        if isinstance(media, tuple):
            publish_many = getattr(self.publisher, "publish_many", None)
            result = publish_many(text, media) if publish_many else self.publisher.publish(text, media[0])
        else:
            result = self.publisher.publish(text, media)
        self.post_repository.record(result)
        return result
