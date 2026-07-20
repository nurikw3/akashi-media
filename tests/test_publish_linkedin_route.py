"""HTTP slice: POST /publish/linkedin (edited text + original media → fake)."""

import base64
import io


def _png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def test_publish_linkedin_requires_login(client):
    resp = client.post(
        "/publish/linkedin",
        data={"linkedin_text": "hi"},
        files={"media": ("p.png", io.BytesIO(_png()), "image/png")},
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_publish_linkedin_success_fragment(auth_client):
    resp = auth_client.post(
        "/publish/linkedin",
        data={"linkedin_text": "Деловой пост для LinkedIn"},
        files={"media": ("p.png", io.BytesIO(_png()), "image/png")},
    )
    assert resp.status_code == 200
    assert "alert--ok" in resp.text
    assert "fake-linkedin-1" in resp.text


def test_publish_linkedin_accepts_multiple_images_for_pdf(auth_client):
    resp = auth_client.post(
        "/publish/linkedin",
        data={"linkedin_text": "Карусель в PDF"},
        files=[
            ("media", ("one.png", io.BytesIO(_png()), "image/png")),
            ("media", ("two.png", io.BytesIO(_png()), "image/png")),
        ],
    )
    assert resp.status_code == 200
    assert "alert--ok" in resp.text


def test_publish_linkedin_rejects_empty_text(auth_client):
    resp = auth_client.post(
        "/publish/linkedin",
        data={"linkedin_text": "   "},
        files={"media": ("p.png", io.BytesIO(_png()), "image/png")},
    )
    assert resp.status_code == 200
    assert "alert--error" in resp.text


def test_publish_linkedin_requires_media(auth_client):
    resp = auth_client.post("/publish/linkedin", data={"linkedin_text": "text"})
    assert resp.status_code == 422
