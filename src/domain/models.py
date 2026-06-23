"""Pure domain models. No imports from adapters, entrypoints, or external SDKs.

Everything here is immutable (frozen dataclasses) per the coding-style contract:
build new objects, never mutate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
