"""HTTP slice: POST /publish/instagram (multipart upload → fake publisher)."""

import io


def _png_bytes() -> bytes:
    # Minimal valid-enough PNG signature; MediaFile only checks content-type + non-empty.
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_publish_instagram_requires_login(client):
    resp = client.post(
        "/publish/instagram",
        data={"source_text": "hi"},
        files={"media": ("p.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_publish_instagram_success_fragment(auth_client):
    resp = auth_client.post(
        "/publish/instagram",
        data={"source_text": "Запуск продукта"},
        files={"media": ("p.png", io.BytesIO(_png_bytes()), "image/png")},
    )
    assert resp.status_code == 200
    assert "alert--ok" in resp.text
    assert "Опубликовано" in resp.text
    assert "fake-instagram-1" in resp.text  # fake publisher external id


def test_publish_instagram_rejects_non_image(auth_client):
    resp = auth_client.post(
        "/publish/instagram",
        data={"source_text": "text"},
        files={"media": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert resp.status_code == 200
    assert "alert--error" in resp.text


def test_publish_instagram_rejects_forged_content_type(auth_client):
    # Declares image/png but the bytes are not a PNG — magic-byte check must reject.
    resp = auth_client.post(
        "/publish/instagram",
        data={"source_text": "text"},
        files={"media": ("evil.png", io.BytesIO(b"<?php echo 1; ?>"), "image/png")},
    )
    assert resp.status_code == 200
    assert "alert--error" in resp.text


def test_publish_instagram_requires_media(auth_client):
    resp = auth_client.post("/publish/instagram", data={"source_text": "text"})
    assert resp.status_code == 422  # missing required file
