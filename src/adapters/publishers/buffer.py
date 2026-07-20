"""Image-post publisher for Buffer's GraphQL API.

One adapter serves any Buffer-connected channel.  The composition root binds a
separate instance for each domain channel, keeping Buffer channel IDs out of
the domain and application layers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from pathlib import Path
from typing import Any

from src.domain.errors import PublishError
from src.domain.models import Channel, MediaFile, PublishResult

BUFFER_API_URL = "https://api.buffer.com"
_CHANNEL_LABELS = {
    Channel.INSTAGRAM: "Instagram",
    Channel.LINKEDIN: "LinkedIn",
}
logger = logging.getLogger(__name__)

_CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess {
      post { id text dueAt }
    }
    ... on MutationError {
      message
    }
  }
}
"""


class BufferPublisher:
    """Publish one image post immediately to a configured Buffer channel."""

    def __init__(
        self,
        http_client: Any,
        api_key: str,
        channel_id: str,
        channel: Channel,
        resolve_image_url: Callable[[MediaFile], str],
    ) -> None:
        self._http = http_client
        self._api_key = api_key
        self._channel_id = channel_id
        self._channel = channel
        self._resolve_image_url = resolve_image_url

    @property
    def channel(self) -> Channel:
        return self._channel

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        """Ask Buffer to publish now, returning only non-sensitive errors."""
        return self._publish_assets(text, (media,))

    def publish_many(self, text: str, media_files: tuple[MediaFile, ...]) -> PublishResult:
        """Publish an Instagram carousel or a LinkedIn PDF document."""
        if not media_files:
            return self._failed()
        if self._channel is Channel.LINKEDIN:
            documents = tuple(item for item in media_files if item.content_type == "application/pdf")
            thumbnails = tuple(item for item in media_files if item.content_type.startswith("image/"))
            if len(documents) != 1 or not thumbnails:
                return self._failed("Для PDF-публикации LinkedIn нужна фотография обложки")
            return self._publish_document(text, documents[0], thumbnails[0])
        return self._publish_assets(text, media_files)

    def _publish_document(
        self, text: str, document: MediaFile, thumbnail: MediaFile
    ) -> PublishResult:
        try:
            document_url = self._resolve_image_url(document)
            thumbnail_url = self._resolve_image_url(thumbnail)
        except PublishError as exc:
            return PublishResult.failed(self._channel, detail=str(exc))
        except Exception:  # noqa: BLE001 - resolver details may be sensitive
            return self._failed()

        title = Path(document.filename).stem.replace("-", " ").strip() or "LinkedIn document"
        return self._send(
            text,
            [
                {
                    "document": {
                        "url": document_url,
                        "title": title[:100],
                        "thumbnailUrl": thumbnail_url,
                    }
                }
            ],
        )

    def _publish_assets(self, text: str, media_files: tuple[MediaFile, ...]) -> PublishResult:
        try:
            assets = []
            for media in media_files:
                url = self._resolve_image_url(media)
                if media.content_type == "application/pdf":
                    assets.append({"document": {"url": url}})
                else:
                    assets.append({"image": {"url": url}})
        except PublishError as exc:
            return PublishResult.failed(self._channel, detail=str(exc))
        except Exception:  # noqa: BLE001 - resolver details may be sensitive
            return self._failed()

        return self._send(text, assets)

    def _send(self, text: str, assets: list[dict[str, Any]]) -> PublishResult:
        post_input: dict[str, Any] = {
            "text": text,
            "channelId": self._channel_id,
            "schedulingType": "automatic",
            "assets": assets,
            # addToQueue waits for the next queue slot. shareNow is the Buffer
            # operation for immediate publication.
            "mode": "shareNow",
        }
        if self._channel is Channel.INSTAGRAM:
            post_input["metadata"] = {
                "instagram": {"type": "post", "shouldShareToFeed": True}
            }
        variables = {"input": post_input}

        try:
            response = self._http.post(
                BUFFER_API_URL,
                json={"query": _CREATE_POST_MUTATION, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "akashimedia/1.0",
                },
            )
            response.raise_for_status()
            payload = response.json()
            post_id = self._post_id(payload)
        except Exception as exc:  # noqa: BLE001 - never expose token/API response details
            logger.error(
                "Buffer publish failed: channel=%s error_type=%s status=%s",
                self._channel.value,
                type(exc).__name__,
                getattr(getattr(exc, "response", None), "status_code", None),
            )
            return self._failed()

        return PublishResult.ok(self._channel, external_id=post_id)

    def _post_id(self, payload: Any) -> str:
        if not isinstance(payload, Mapping) or payload.get("errors"):
            raise ValueError("Buffer returned a GraphQL error")

        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("Buffer response is missing data")
        result = data.get("createPost")
        if not isinstance(result, Mapping) or result.get("message"):
            raise ValueError("Buffer rejected the post")
        post = result.get("post")
        if not isinstance(post, Mapping):
            raise ValueError("Buffer response is missing a post")
        post_id = post.get("id")
        if not isinstance(post_id, str) or not post_id:
            raise ValueError("Buffer response is missing a post id")
        return post_id

    def _failed(self, detail: str | None = None) -> PublishResult:
        return PublishResult.failed(
            self._channel,
            detail=detail
            or f"Не удалось опубликовать в {_CHANNEL_LABELS[self._channel]} через Buffer",
        )
