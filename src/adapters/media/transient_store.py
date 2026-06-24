"""TransientMediaStore — short-lived in-memory hold for media in transit.

Instagram's Graph API fetches the image server-side from a public URL; it never
receives the raw bytes. So between "user uploaded bytes" and "Instagram fetched
the URL" the bytes must live *somewhere* reachable. Per the Phase-1 contract the
platform persists nothing, so this is RAM-only with a short TTL — long enough for
Instagram to fetch, then gone. Tokens are unguessable; the public /media route
serves strictly what was put here.
"""

from __future__ import annotations

import secrets
import time
from typing import Callable

from src.domain.models import MediaFile

# Long enough for the Graph API to fetch the container image, short enough that a
# leaked URL stops working quickly. Media is transit-only — never persisted.
DEFAULT_TTL_SECONDS = 600


class TransientMediaStore:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._now = now
        self._items: dict[str, tuple[float, MediaFile]] = {}

    def put(self, media: MediaFile) -> str:
        """Store media under a fresh unguessable token; return the token."""
        self._prune()
        token = secrets.token_urlsafe(24)
        self._items[token] = (self._now() + self._ttl, media)
        return token

    def get(self, token: str) -> MediaFile | None:
        """Return live media for a token, or None if unknown or expired."""
        self._prune()
        item = self._items.get(token)
        return item[1] if item is not None else None

    def _prune(self) -> None:
        now = self._now()
        for token in [t for t, (expires, _) in self._items.items() if expires <= now]:
            del self._items[token]
