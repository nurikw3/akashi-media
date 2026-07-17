"""Pure domain models. No imports from adapters, entrypoints, or external SDKs.

Everything here is immutable (frozen dataclasses) per the coding-style contract:
build new objects, never mutate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse


class Channel(str, Enum):
    """A publishing destination. The string value is the Factory selector."""

    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"


# Explicit allowlist — excludes image/svg+xml, which can carry scripts.
ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)


@dataclass(frozen=True, slots=True)
class MediaFile:
    """An in-memory media file moving through the transit gateway.

    The platform persists nothing (Scope Cut: no DB) — bytes live only for the
    duration of a single publish request.
    """

    filename: str
    content_type: str
    data: bytes

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("MediaFile.data must not be empty")
        if self.content_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError(
                f"Unsupported media type {self.content_type!r}; "
                f"allowed: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}"
            )


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Outcome of a publish attempt against one channel."""

    channel: Channel
    success: bool
    external_id: str | None = None
    detail: str | None = None

    @classmethod
    def ok(cls, channel: Channel, external_id: str, detail: str | None = None) -> "PublishResult":
        return cls(channel=channel, success=True, external_id=external_id, detail=detail)

    @classmethod
    def failed(cls, channel: Channel, detail: str) -> "PublishResult":
        return cls(channel=channel, success=False, external_id=None, detail=detail)


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A source article candidate for one data-center digest post."""

    title: str
    url: str
    summary: str
    published_at: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("NewsItem.title must not be empty")
        if not self.summary.strip():
            raise ValueError("NewsItem.summary must not be empty")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("NewsItem.url must be an absolute HTTP(S) URL")


@dataclass(frozen=True, slots=True)
class TextPublishResult:
    """Outcome of publishing one text-only post."""

    success: bool
    external_id: str | None = None
    detail: str | None = None

    @classmethod
    def ok(cls, external_id: str) -> "TextPublishResult":
        return cls(success=True, external_id=external_id)

    @classmethod
    def failed(cls, detail: str) -> "TextPublishResult":
        return cls(success=False, detail=detail)


@dataclass(frozen=True, slots=True)
class DigestPublishReport:
    """Summary returned to the operator after one manual digest run."""

    candidates: int
    attempted: int
    published: int
    failed: int


@dataclass(frozen=True, slots=True)
class DigestPublication:
    title: str
    source_name: str
    source_url: str
    source_published_at: str | None
    status: str
    telegram_message_id: str | None
    created_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class DigestRun:
    trigger: str
    candidates: int
    attempted: int
    published: int
    failed: int
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class DigestDashboard:
    total_published: int
    published_today: int
    last_run: DigestRun | None
    publications: tuple[DigestPublication, ...]
