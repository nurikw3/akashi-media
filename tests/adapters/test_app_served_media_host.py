"""AppServedMediaHost — builds an app-owned URL and stores the bytes for it."""

import pytest

from src.adapters.media.app_served_media_host import AppServedMediaHost
from src.adapters.media.transient_store import TransientMediaStore
from src.domain.errors import PublishError
from src.domain.models import MediaFile

MEDIA = MediaFile(filename="p.png", content_type="image/png", data=b"\x89PNG\r\n\x1a\nbytes")


def test_host_returns_app_url_and_stores_media():
    store = TransientMediaStore()
    host = AppServedMediaHost(store, "https://akashi.example")

    url = host.host(MEDIA)

    assert url.startswith("https://akashi.example/media/")
    token = url.rsplit("/", 1)[1]
    assert store.get(token) is MEDIA


def test_trailing_slash_in_base_is_normalized():
    host = AppServedMediaHost(TransientMediaStore(), "https://akashi.example/")

    assert "https://akashi.example/media/" in host.host(MEDIA)
    assert "//media/" not in host.host(MEDIA).replace("https://", "")


def test_non_https_base_is_rejected():
    with pytest.raises(PublishError, match="https"):
        AppServedMediaHost(TransientMediaStore(), "http://akashi.example")
