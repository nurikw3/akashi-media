import base64

from src.adapters.media.pillow_pdf import PillowPdfConverter
from src.domain.models import MediaFile


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_images_to_pdf_returns_one_multi_page_document():
    converter = PillowPdfConverter()
    pdf = converter.images_to_pdf(
        (
            MediaFile("one.png", "image/png", _PNG),
            MediaFile("two.png", "image/png", _PNG),
        )
    )
    assert pdf.content_type == "application/pdf"
    assert pdf.filename == "linkedin-carousel.pdf"
    assert pdf.data.startswith(b"%PDF")
