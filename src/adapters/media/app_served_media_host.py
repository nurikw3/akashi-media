"""Resolve a MediaFile to a short-lived public URL served by this app.

Bytes go into a TransientMediaStore; the returned URL points at this app's own
``/media/{token}`` route for Instagram Graph or Buffer to fetch server-side.
Keeping the host app-owned prevents user-controlled hosts from reaching either
publishing API.
"""

from __future__ import annotations

from src.adapters.media.transient_store import TransientMediaStore
from src.domain.errors import PublishError
from src.domain.models import MediaFile


class AppServedMediaHost:
    def __init__(self, store: TransientMediaStore, public_base_url: str) -> None:
        # Publishing APIs fetch over HTTPS; reject a non-HTTPS base loudly at
        # construction (composition root) instead of failing later.
        if not public_base_url.startswith("https://"):
            raise PublishError("PUBLIC_BASE_URL must be an https:// URL for media publishing")
        self._store = store
        self._base = public_base_url.rstrip("/")

    def host(self, media: MediaFile) -> str:
        token = self._store.put(media)
        return f"{self._base}/media/{token}"
