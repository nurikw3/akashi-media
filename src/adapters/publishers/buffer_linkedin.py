"""LinkedIn publisher through the Buffer GraphQL API.

The supplied Buffer script creates text posts in a connected channel's queue.
Buffer owns the channel credentials and scheduling; our PublisherPort remains
immediate from the application's perspective because Buffer accepts the post
in one API call. Buffer's mutation in this integration accepts text only, so
the required MediaFile is intentionally not sent.
"""

from __future__ import annotations

import json
from typing import Any

from src.domain.models import Channel, MediaFile, PublishResult

BUFFER_API_URL = "https://api.buffer.com"


class BufferLinkedInPublisher:
    def __init__(self, http_client: Any, api_key: str, channel_id: str) -> None:
        self._http = http_client
        self._api_key = api_key
        self._channel_id = channel_id

    @property
    def channel(self) -> Channel:
        return Channel.LINKEDIN

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        """Queue a text post in Buffer without exposing token details to users."""
        del media  # Buffer's provided mutation publishes text-only posts.
        query = self._create_post_query(text)
        try:
            response = self._http.post(
                BUFFER_API_URL,
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "akashimedia/1.0",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise ValueError("Buffer GraphQL returned errors")
            result = payload.get("data", {}).get("createPost", {})
            if result.get("message"):
                raise ValueError("Buffer rejected the post")
            post = result.get("post") or {}
            post_id = post.get("id")
            if not post_id:
                raise ValueError("Buffer response missing post id")
        except Exception:  # noqa: BLE001 - do not expose response/token details
            return PublishResult.failed(
                Channel.LINKEDIN,
                detail="Не удалось передать публикацию в Buffer для LinkedIn",
            )
        return PublishResult.ok(Channel.LINKEDIN, external_id=post_id)

    def _create_post_query(self, text: str) -> str:
        return f"""
        mutation CreatePost {{
          createPost(input: {{
            text: {json.dumps(text, ensure_ascii=False)},
            channelId: {json.dumps(self._channel_id)},
            schedulingType: automatic,
            assets: [],
            mode: addToQueue
          }}) {{
            ... on PostActionSuccess {{
              post {{ id text dueAt }}
            }}
            ... on MutationError {{
              message
            }}
          }}
        }}
        """
