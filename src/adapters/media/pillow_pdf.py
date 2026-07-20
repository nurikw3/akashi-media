"""High-fidelity in-memory PDF assembly for LinkedIn document posts."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

from src.domain.models import MediaFile


class PillowPdfConverter:
    """Create a multi-page PDF without resizing source images."""

    def images_to_pdf(self, media_files: tuple[MediaFile, ...]) -> MediaFile:
        if not media_files:
            raise ValueError("At least one image is required")
        pages: list[Image.Image] = []
        try:
            for media in media_files:
                if not media.content_type.startswith("image/"):
                    raise ValueError("Only images can be converted to PDF")
                try:
                    image = Image.open(BytesIO(media.data))
                except (OSError, ValueError) as exc:
                    raise ValueError("Изображение повреждено или имеет неподдерживаемый формат") from exc
                image.load()
                pages.append(ImageOps.exif_transpose(image).convert("RGB"))
            output = BytesIO()
            pages[0].save(
                output,
                format="PDF",
                save_all=True,
                append_images=pages[1:],
                resolution=300.0,
                quality=100,
                subsampling=0,
            )
            return MediaFile("linkedin-carousel.pdf", "application/pdf", output.getvalue())
        finally:
            for page in pages:
                page.close()
