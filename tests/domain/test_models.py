import pytest

from src.domain.models import Channel, MediaFile, PublishResult


def test_mediafile_accepts_image():
    media = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff")
    assert media.filename == "p.jpg"


def test_mediafile_accepts_pdf_for_linkedin_documents():
    media = MediaFile(filename="doc.pdf", content_type="application/pdf", data=b"%PDF-1.4")
    assert media.content_type == "application/pdf"


def test_mediafile_rejects_unknown_type():
    with pytest.raises(ValueError):
        MediaFile(filename="doc.txt", content_type="text/plain", data=b"x")


def test_mediafile_rejects_svg_xss_vector():
    with pytest.raises(ValueError):
        MediaFile(filename="x.svg", content_type="image/svg+xml", data=b"<svg/>")


def test_mediafile_rejects_empty_data():
    with pytest.raises(ValueError):
        MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"")


def test_mediafile_is_immutable():
    media = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"x")
    with pytest.raises(Exception):
        media.filename = "other.jpg"  # type: ignore[misc]


def test_publishresult_ok_and_failed():
    ok = PublishResult.ok(Channel.INSTAGRAM, external_id="123")
    assert ok.success and ok.external_id == "123"

    bad = PublishResult.failed(Channel.LINKEDIN, detail="boom")
    assert not bad.success and bad.detail == "boom"


def test_channel_value_is_factory_selector():
    assert Channel.INSTAGRAM.value == "instagram"
    assert Channel.LINKEDIN.value == "linkedin"
