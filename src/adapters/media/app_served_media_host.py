"""AppServedMediaHost — resolves a MediaFile to a public URL served by this app.

Satisfies the InstagramGraphPublisher's `resolve_image_url` seam. Bytes go into a
TransientMediaStore; the returned URL points at this app's own /media/{token}
route, which the Graph API fetches server-side. Keeping the host app-owned is the
SSRF guard the publisher documents: no user-controlled host ever reaches Graph.
"""

from __future__ import annotations

from src.adapters.media.transient_store import TransientMediaStore
from src.domain.errors import PublishError
from src.domain.models import MediaFile


class AppServedMediaHost:
    def __init__(self, store: TransientMediaStore, public_base_url: str) -> None:
        # Graph fetches over HTTPS only; a non-HTTPS base would silently fail the
        # fetch, so reject it loudly at construction (composition root) instead.
        if not public_base_url.startswith("https://"):
            raise PublishError("PUBLIC_BASE_URL must be an https:// URL for Instagram media")
        self._store = store
        self._base = public_base_url.rstrip("/")

    def host(self, media: MediaFile) -> str:
        token = self._store.put(media)
        return f"{self._base}/media/{token}"
