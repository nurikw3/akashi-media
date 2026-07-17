from src.adapters.publishers.buffer_linkedin import BufferLinkedInPublisher
from src.domain.models import Channel, MediaFile

MEDIA = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff\xe0BYTES")


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class _Http:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, json=None, headers=None):
        self.requests.append({"url": url, "json": json, "headers": headers})
        return self.response


def test_buffer_publisher_queues_text_post_and_returns_buffer_id():
    http = _Http(_Response({"data": {"createPost": {"post": {"id": "post-42"}}}}))
    publisher = BufferLinkedInPublisher(http, api_key="buffer-secret", channel_id="channel-7")

    result = publisher.publish("Деловой пост", MEDIA)

    assert result.success is True
    assert result.channel is Channel.LINKEDIN
    assert result.external_id == "post-42"
    request = http.requests[0]
    assert request["url"] == "https://api.buffer.com"
    assert "channel-7" in request["json"]["query"]
    assert "Деловой пост" in request["json"]["query"]
    assert "assets: []" in request["json"]["query"]
    assert request["headers"]["Authorization"] == "Bearer buffer-secret"


def test_buffer_publisher_hides_api_error_details():
    http = _Http(_Response({"errors": [{"message": "token invalid"}]}))
    result = BufferLinkedInPublisher(http, api_key="buffer-secret", channel_id="channel-7").publish(
        "text", MEDIA
    )

    assert result.success is False
    assert "buffer-secret" not in (result.detail or "")


def test_buffer_publisher_satisfies_port():
    from src.domain.ports.publisher import PublisherPort

    assert isinstance(BufferLinkedInPublisher(_Http(_Response({})), "key", "channel"), PublisherPort)
