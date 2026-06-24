"""GET /media/{token} — public route the Graph API fetches image bytes from."""

from src.domain.models import MediaFile

MEDIA = MediaFile(filename="p.png", content_type="image/png", data=b"\x89PNG\r\n\x1a\npayload")


def test_media_route_serves_stored_bytes_without_login(app, client):
    token = app.state.container.media_store.put(MEDIA)

    resp = client.get(f"/media/{token}")

    assert resp.status_code == 200
    assert resp.content == MEDIA.data
    assert resp.headers["content-type"].startswith("image/png")


def test_media_route_returns_404_for_unknown_token(client):
    assert client.get("/media/does-not-exist").status_code == 404
