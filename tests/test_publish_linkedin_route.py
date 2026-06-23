"""HTTP slice: POST /publish/linkedin (edited text + original media → fake)."""

import io


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


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
