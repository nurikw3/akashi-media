"""InstagramGraphPublisher tested against a stub HTTP client — no real network."""

import pytest

from src.adapters.publishers.instagram import InstagramGraphPublisher
from src.domain.models import Channel, MediaFile

MEDIA = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff\xe0")


class _StubResponse:
    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


class _StubHttp:
    """Records POSTs and returns queued responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, data=None, **kwargs):
        self.calls.append({"url": url, "data": data})
        return self._responses.pop(0)


def _resolver(_media):
    return "https://cdn.example.test/p.jpg"


def test_publish_runs_two_step_graph_flow_and_returns_id():
    http = _StubHttp([
        _StubResponse({"id": "CREATION_123"}),   # create container
        _StubResponse({"id": "MEDIA_999"}),       # publish container
    ])
    pub = InstagramGraphPublisher(
        http_client=http, token="TOK", ig_user_id="IGUSER", resolve_image_url=_resolver
    )

    result = pub.publish("Привет 🚀", MEDIA)

    assert result.success is True
    assert result.channel is Channel.INSTAGRAM
    assert result.external_id == "MEDIA_999"
    # First call creates the container with caption + resolved image url.
    create = http.calls[0]
    assert "IGUSER/media" in create["url"]
    assert create["data"]["caption"] == "Привет 🚀"
    assert create["data"]["image_url"] == "https://cdn.example.test/p.jpg"
    # Second call publishes using the creation id from step one.
    publish = http.calls[1]
    assert "media_publish" in publish["url"]
    assert publish["data"]["creation_id"] == "CREATION_123"


def test_publish_returns_failed_on_http_error_without_leaking_token():
    http = _StubHttp([_StubResponse({"error": "bad"}, status=400)])
    pub = InstagramGraphPublisher(
        http_client=http, token="SUPERSECRET", ig_user_id="IGUSER", resolve_image_url=_resolver
    )

    result = pub.publish("text", MEDIA)

    assert result.success is False
    assert "SUPERSECRET" not in (result.detail or "")


def test_publish_returns_failed_when_media_host_unconfigured():
    from src.domain.errors import PublishError

    def unconfigured(_media):
        raise PublishError("media hosting not configured (Phase 2)")

    http = _StubHttp([])
    pub = InstagramGraphPublisher(
        http_client=http, token="TOK", ig_user_id="IGUSER", resolve_image_url=unconfigured
    )
    result = pub.publish("text", MEDIA)
    assert result.success is False
    assert http.calls == []  # never hit the API


def test_instagram_publisher_satisfies_port():
    from src.domain.ports.publisher import PublisherPort

    pub = InstagramGraphPublisher(
        http_client=_StubHttp([]), token="t", ig_user_id="u", resolve_image_url=_resolver
    )
    assert isinstance(pub, PublisherPort)
