"""TransientMediaStore — token round-trip, TTL expiry, unknown tokens."""

from src.adapters.media.transient_store import TransientMediaStore
from src.domain.models import MediaFile

MEDIA = MediaFile(filename="p.png", content_type="image/png", data=b"\x89PNG\r\n\x1a\nbytes")


def test_put_then_get_returns_same_media():
    store = TransientMediaStore()

    token = store.put(MEDIA)

    assert store.get(token) is MEDIA


def test_get_unknown_token_returns_none():
    store = TransientMediaStore()

    assert store.get("nope") is None


def test_put_issues_distinct_tokens():
    store = TransientMediaStore()

    assert store.put(MEDIA) != store.put(MEDIA)


def test_media_expires_after_ttl():
    clock = {"t": 1000.0}
    store = TransientMediaStore(ttl_seconds=60, now=lambda: clock["t"])

    token = store.put(MEDIA)
    clock["t"] += 61  # advance past the TTL

    assert store.get(token) is None
