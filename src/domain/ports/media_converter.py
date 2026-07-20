"""Port for turning a collection of uploaded images into a publication asset."""

from __future__ import annotations

from typing import Protocol

from src.domain.models import MediaFile


class MediaConverterPort(Protocol):
    def images_to_pdf(self, media_files: tuple[MediaFile, ...]) -> MediaFile:
        """Return one PDF preserving the source image dimensions and pixels."""
        ...
