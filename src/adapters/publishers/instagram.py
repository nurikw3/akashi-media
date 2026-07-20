"""InstagramGraphPublisher — real Instagram publishing via the Graph API.

The Graph API publishes a feed photo in two steps (create media container →
publish container) and requires a *publicly reachable* image_url; it does not
accept raw bytes. Phase 1 persists nothing, so a `resolve_image_url` callable
supplies a short-lived app-served URL. This adapter is exercised by unit tests
(stub HTTP) and a token-gated integration test.
"""

from __future__ import annotations

from typing import Any, Callable

from src.domain.errors import PublishError
from src.domain.models import Channel, MediaFile, PublishResult

# Instagram API with Instagram Login (graph.instagram.com) — the token is an
# IGAA-prefixed Instagram User token, and ig_user_id is the app-scoped id from
# GET /me. The two-step publish flow is identical to the Facebook-login Graph
# API; only the host and token type differ.
GRAPH_API_BASE = "https://graph.instagram.com/v21.0"


class InstagramGraphPublisher:
    def __init__(
        self,
        http_client: Any,
        token: str,
        ig_user_id: str,
        resolve_image_url: Callable[[MediaFile], str],
    ) -> None:
        # SSRF note: resolve_image_url MUST return a URL on an app-owned CDN
        # allowlist. Never let user-controlled input flow into this URL — the
        # Graph API fetches it server-side.
        self._http = http_client
        self._token = token
        self._ig_user_id = ig_user_id
        self._resolve_image_url = resolve_image_url

    @property
    def channel(self) -> Channel:
        return Channel.INSTAGRAM

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        try:
            image_url = self._resolve_image_url(media)
        except PublishError as exc:
            # Resolver failures carry a safe domain message (e.g. "media hosting
            # not configured") — surface it instead of a generic one.
            return PublishResult.failed(Channel.INSTAGRAM, detail=str(exc))

        try:
            container = self._http.post(
                f"{GRAPH_API_BASE}/{self._ig_user_id}/media",
                data={"image_url": image_url, "caption": text, "access_token": self._token},
            )
            container.raise_for_status()
            creation_id = container.json()["id"]

            published = self._http.post(
                f"{GRAPH_API_BASE}/{self._ig_user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": self._token},
            )
            published.raise_for_status()
            media_id = published.json()["id"]
        except Exception:  # noqa: BLE001
            # Generic detail only — never echo the cause (may contain the token
            # or request body) into a user-visible result.
            return PublishResult.failed(
                Channel.INSTAGRAM, detail="Не удалось опубликовать в Instagram"
            )

        return PublishResult.ok(Channel.INSTAGRAM, external_id=media_id)

    def publish_many(self, text: str, media_files: tuple[MediaFile, ...]) -> PublishResult:
        """Publish up to ten images as an Instagram carousel."""
        if not media_files:
            return PublishResult.failed(Channel.INSTAGRAM, detail="Нет медиа")
        if len(media_files) == 1:
            return self.publish(text, media_files[0])
        if len(media_files) > 10:
            return PublishResult.failed(
                Channel.INSTAGRAM, detail="Instagram поддерживает не более 10 фото в карусели"
            )
        try:
            children: list[str] = []
            for media in media_files:
                image_url = self._resolve_image_url(media)
                child = self._http.post(
                    f"{GRAPH_API_BASE}/{self._ig_user_id}/media",
                    data={
                        "image_url": image_url,
                        "is_carousel_item": "true",
                        "access_token": self._token,
                    },
                )
                child.raise_for_status()
                children.append(child.json()["id"])
            container = self._http.post(
                f"{GRAPH_API_BASE}/{self._ig_user_id}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(children),
                    "caption": text,
                    "access_token": self._token,
                },
            )
            container.raise_for_status()
            creation_id = container.json()["id"]
            published = self._http.post(
                f"{GRAPH_API_BASE}/{self._ig_user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": self._token},
            )
            published.raise_for_status()
            media_id = published.json()["id"]
        except Exception:  # noqa: BLE001
            return PublishResult.failed(
                Channel.INSTAGRAM, detail="Не удалось опубликовать карусель в Instagram"
            )
        return PublishResult.ok(Channel.INSTAGRAM, external_id=media_id)
