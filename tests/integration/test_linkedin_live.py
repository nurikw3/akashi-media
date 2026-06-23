"""Live LinkedIn publish — opt-in, skipped unless real credentials are present.

Needs LI_TOKEN and LI_AUTHOR_URN (e.g. urn:li:person:xxxx). LinkedIn accepts the
binary upload directly, so no external media host is required.

Run with: LI_TOKEN=... LI_AUTHOR_URN=... pytest tests/integration -m live
"""

import os

import pytest

_REQUIRED = ("LI_TOKEN", "LI_AUTHOR_URN")

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in _REQUIRED),
    reason="set LI_TOKEN and LI_AUTHOR_URN to run the live LinkedIn test",
)


@pytest.mark.live
def test_linkedin_live_publish():
    import httpx

    from src.adapters.publishers.linkedin import LinkedInPublisher
    from src.domain.models import MediaFile

    publisher = LinkedInPublisher(
        http_client=httpx.Client(timeout=30.0),
        token=os.environ["LI_TOKEN"],
        author_urn=os.environ["LI_AUTHOR_URN"],
    )
    # A tiny 1x1 PNG.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415408d763f8cfc0f01f0005000119a3d3b30000000049454e44ae426082"
    )
    media = MediaFile(filename="t.png", content_type="image/png", data=png)

    result = publisher.publish("AkashiMedia live test", media)

    assert result.success is True
    assert result.external_id
