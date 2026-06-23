"""Live Instagram publish — opt-in, skipped unless real credentials are present.

Phase-1 decision: real Graph calls live behind this skipped test until tokens
are configured. Needs IG_TOKEN, IG_USER_ID and a publicly reachable TEST_IMAGE_URL
(Graph requires a hosted image_url — Phase-1 has no media host).

Run with: IG_TOKEN=... IG_USER_ID=... TEST_IMAGE_URL=... pytest tests/integration -m live
"""

import os

import pytest

_REQUIRED = ("IG_TOKEN", "IG_USER_ID", "TEST_IMAGE_URL")

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in _REQUIRED),
    reason="set IG_TOKEN, IG_USER_ID and TEST_IMAGE_URL to run the live Instagram test",
)


@pytest.mark.live
def test_instagram_live_publish():
    import httpx

    from src.adapters.publishers.instagram import InstagramGraphPublisher
    from src.domain.models import MediaFile

    publisher = InstagramGraphPublisher(
        http_client=httpx.Client(timeout=30.0),
        token=os.environ["IG_TOKEN"],
        ig_user_id=os.environ["IG_USER_ID"],
        resolve_image_url=lambda _media: os.environ["TEST_IMAGE_URL"],
    )
    media = MediaFile(filename="t.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff")

    result = publisher.publish("AkashiMedia live test", media)

    assert result.success is True
    assert result.external_id
