"""BufferPublisher unit tests use stubs only; no live posts are created."""

import pytest

from src.adapters.publishers.buffer import BufferPublisher
from src.domain.errors import PublishError
from src.domain.models import Channel, MediaFile

MEDIA = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff\xe0BYTES")
PDF = MediaFile(filename="linkedin-carousel.pdf", content_type="application/pdf", data=b"%PDF-1.4")
IMAGE_URL = "https://akashi.example/media/image-token"


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error containing SUPERSECRET")

    def json(self):
        return self._payload


class _Http:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, json=None, headers=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        return self.response


def _publisher(http, channel=Channel.LINKEDIN, resolver=lambda _media: IMAGE_URL):
    return BufferPublisher(
        http_client=http,
        api_key="buffer-secret",
        channel_id=f"channel-{channel.value}",
        channel=channel,
        resolve_image_url=resolver,
    )


@pytest.mark.parametrize("channel", [Channel.LINKEDIN, Channel.INSTAGRAM])
def test_buffer_publisher_shares_image_post_now(channel):
    http = _Http(_Response({"data": {"createPost": {"post": {"id": "post-42"}}}}))
    resolved_media = []
    publisher = _publisher(
        http,
        channel,
        resolver=lambda media: resolved_media.append(media) or IMAGE_URL,
    )

    result = publisher.publish('Деловой пост "с кавычками"', MEDIA)

    assert result.success is True
    assert result.channel is channel
    assert result.external_id == "post-42"
    assert resolved_media == [MEDIA]
    request = http.requests[0]
    assert request["url"] == "https://api.buffer.com"
    assert request["headers"]["Authorization"] == "Bearer buffer-secret"
    assert "$input: CreatePostInput!" in request["json"]["query"]
    assert "addToQueue" not in request["json"]["query"]
    expected_input = {
        "text": 'Деловой пост "с кавычками"',
        "channelId": f"channel-{channel.value}",
        "schedulingType": "automatic",
        "assets": [{"image": {"url": IMAGE_URL}}],
        "mode": "shareNow",
    }
    if channel is Channel.INSTAGRAM:
        expected_input["metadata"] = {
            "instagram": {"type": "post", "shouldShareToFeed": True}
        }
    assert request["json"]["variables"] == {"input": expected_input}


@pytest.mark.parametrize(
    "payload",
    [
        {"errors": [{"message": "token invalid: buffer-secret"}]},
        {"data": {"createPost": {"message": "channel rejected buffer-secret"}}},
        {"data": {"createPost": {"post": {}}}},
        {"data": None},
        ["not", "a", "mapping"],
    ],
)
def test_buffer_publisher_handles_graphql_and_malformed_errors_safely(payload):
    result = _publisher(_Http(_Response(payload))).publish("text", MEDIA)

    assert result.success is False
    assert result.external_id is None
    assert "buffer-secret" not in (result.detail or "")
    assert "channel rejected" not in (result.detail or "")


def test_buffer_publisher_handles_http_errors_safely():
    result = _publisher(_Http(_Response({}, status=401))).publish("text", MEDIA)

    assert result.success is False
    assert "SUPERSECRET" not in (result.detail or "")


def test_buffer_publisher_sends_linkedin_pdf_with_title_and_thumbnail():
    http = _Http(_Response({"data": {"createPost": {"post": {"id": "post-pdf"}}}}))
    resolved = {
        "linkedin-carousel.pdf": "https://akashi.example/media/document-token",
        "p.jpg": "https://akashi.example/media/thumbnail-token",
    }
    publisher = _publisher(http, resolver=lambda media: resolved[media.filename])

    result = publisher.publish_many("LinkedIn document", (PDF, MEDIA))

    assert result.success is True
    document = http.requests[0]["json"]["variables"]["input"]["assets"][0]["document"]
    assert document == {
        "url": "https://akashi.example/media/document-token",
        "title": "linkedin carousel",
        "thumbnailUrl": "https://akashi.example/media/thumbnail-token",
    }


def test_buffer_publisher_requires_thumbnail_for_linkedin_pdf():
    http = _Http(_Response({}))

    result = _publisher(http).publish_many("LinkedIn document", (PDF,))

    assert result.success is False
    assert "обложки" in (result.detail or "")
    assert http.requests == []


def test_buffer_publisher_surfaces_safe_media_configuration_error_without_api_call():
    http = _Http(_Response({}))

    def unconfigured(_media):
        raise PublishError("PUBLIC_BASE_URL не настроен")

    result = _publisher(http, resolver=unconfigured).publish("text", MEDIA)

    assert result.success is False
    assert result.detail == "PUBLIC_BASE_URL не настроен"
    assert http.requests == []


def test_buffer_publisher_hides_unexpected_resolver_error():
    http = _Http(_Response({}))

    def broken(_media):
        raise RuntimeError("private resolver details")

    result = _publisher(http, resolver=broken).publish("text", MEDIA)

    assert result.success is False
    assert "private resolver details" not in (result.detail or "")
    assert http.requests == []


def test_buffer_publisher_satisfies_port():
    from src.domain.ports.publisher import PublisherPort

    assert isinstance(_publisher(_Http(_Response({}))), PublisherPort)
