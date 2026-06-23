"""LinkedInPublisher tested against a stub HTTP client — no real network."""

from src.adapters.publishers.linkedin import LinkedInPublisher
from src.domain.models import Channel, MediaFile

MEDIA = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff\xe0BYTES")


class _StubResponse:
    def __init__(self, json_data=None, status=200, headers=None):
        self._json = json_data or {}
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


class _StubHttp:
    def __init__(self, post_responses, put_response):
        self._posts = list(post_responses)
        self._put = put_response
        self.posts = []
        self.puts = []

    def post(self, url, json=None, headers=None, **kwargs):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return self._posts.pop(0)

    def put(self, url, content=None, headers=None, **kwargs):
        self.puts.append({"url": url, "content": content, "headers": headers})
        return self._put


def _publisher(http):
    return LinkedInPublisher(http_client=http, token="LITOKEN", author_urn="urn:li:person:ABC")


def test_publish_runs_three_step_flow_and_returns_post_id():
    http = _StubHttp(
        post_responses=[
            _StubResponse(
                {"value": {"uploadUrl": "https://api.linkedin.com/up/abc", "image": "urn:li:image:IMG1"}}
            ),
            _StubResponse(headers={"x-restli-id": "urn:li:share:POST99"}),
        ],
        put_response=_StubResponse(status=201),
    )
    result = _publisher(http).publish("Деловой пост", MEDIA)

    assert result.success is True
    assert result.channel is Channel.LINKEDIN
    assert result.external_id == "urn:li:share:POST99"
    # Step 2 PUTs the raw image bytes to the returned upload URL.
    assert http.puts[0]["url"] == "https://api.linkedin.com/up/abc"
    assert http.puts[0]["content"] == MEDIA.data
    # Step 3 creates the post referencing the uploaded image urn + commentary.
    create = http.posts[1]["json"]
    assert create["commentary"] == "Деловой пост"
    assert create["author"] == "urn:li:person:ABC"
    assert "urn:li:image:IMG1" in str(create)


def test_publish_sends_bearer_token_in_header_not_leaked_on_error():
    http = _StubHttp(post_responses=[_StubResponse(status=401)], put_response=_StubResponse())
    result = _publisher(http).publish("text", MEDIA)

    assert result.success is False
    assert "LITOKEN" not in (result.detail or "")
    # Token is carried via Authorization header, never the URL.
    assert "Bearer LITOKEN" in http.posts[0]["headers"]["Authorization"]


def test_publish_rejects_untrusted_upload_url():
    http = _StubHttp(
        post_responses=[
            _StubResponse({"value": {"uploadUrl": "https://evil.example/steal", "image": "urn:li:image:X"}}),
        ],
        put_response=_StubResponse(),
    )
    result = _publisher(http).publish("text", MEDIA)
    assert result.success is False
    assert http.puts == []  # token never sent to the untrusted host


def test_publish_fails_when_post_id_missing():
    http = _StubHttp(
        post_responses=[
            _StubResponse({"value": {"uploadUrl": "https://api.linkedin.com/up/x", "image": "urn:li:image:X"}}),
            _StubResponse(json_data={}, headers={}),  # no x-restli-id, no id
        ],
        put_response=_StubResponse(status=201),
    )
    result = _publisher(http).publish("text", MEDIA)
    assert result.success is False


def test_linkedin_publisher_satisfies_port():
    from src.domain.ports.publisher import PublisherPort

    assert isinstance(_publisher(_StubHttp([], _StubResponse())), PublisherPort)
