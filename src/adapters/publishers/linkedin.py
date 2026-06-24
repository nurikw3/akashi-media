"""LinkedInPublisher — real LinkedIn publishing via the Posts/Images API.

Unlike Instagram, LinkedIn accepts binary uploads, so the in-memory bytes are
posted directly (no media host needed): three steps —
  1. initialize an image upload for the author,
  2. PUT the raw image bytes to the returned upload URL,
  3. create the post referencing the uploaded image URN + commentary.

Token-gated: the composition root binds FakePublisher unless LI_TOKEN and
LI_AUTHOR_URN are set. The injected http client keeps this unit-testable.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from src.domain.models import Channel, MediaFile, PublishResult

LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202506"


def _is_trusted_upload_url(url: str) -> bool:
    """Defense in depth: only PUT bytes (with the Bearer token) to a LinkedIn host."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host == "linkedin.com" or host.endswith(".linkedin.com"))


class LinkedInPublisher:
    def __init__(self, http_client: Any, token: str, author_urn: str) -> None:
        self._http = http_client
        self._token = token
        self._author_urn = author_urn

    @property
    def channel(self) -> Channel:
        return Channel.LINKEDIN

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def publish(self, text: str, media: MediaFile) -> PublishResult:
        try:
            init = self._http.post(
                f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
                json={"initializeUploadRequest": {"owner": self._author_urn}},
                headers=self._headers(),
            )
            init.raise_for_status()
            value = init.json()["value"]
            upload_url = value["uploadUrl"]
            image_urn = value["image"]

            if not _is_trusted_upload_url(upload_url):
                raise ValueError("Untrusted LinkedIn upload URL")

            uploaded = self._http.put(
                upload_url,
                content=media.data,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            uploaded.raise_for_status()

            created = self._http.post(
                f"{LINKEDIN_API_BASE}/rest/posts",
                json={
                    "author": self._author_urn,
                    "commentary": text,
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MAIN_FEED",
                        "targetEntities": [],
                        "thirdPartyDistributionChannels": [],
                    },
                    "content": {"media": {"id": image_urn}},
                    "lifecycleState": "PUBLISHED",
                },
                headers=self._headers(),
            )
            created.raise_for_status()
            post_id = created.headers.get("x-restli-id") or created.json().get("id")
            if not post_id:
                raise ValueError("LinkedIn response missing post id")
        except Exception:  # noqa: BLE001
            # Generic detail only — never echo the cause (token / request body).
            return PublishResult.failed(
                Channel.LINKEDIN, detail="Не удалось опубликовать в LinkedIn"
            )

        return PublishResult.ok(Channel.LINKEDIN, external_id=post_id)
