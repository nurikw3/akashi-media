"""Security-hardening behavior for the auth scaffold."""

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, create_app
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["content-security-policy"]


def test_session_cookie_is_strict_samesite(client):
    resp = client.post("/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    set_cookie = resp.headers.get("set-cookie", "")
    assert "samesite=strict" in set_cookie.lower()
    assert "httponly" in set_cookie.lower()


def test_login_rate_limited_after_repeated_failures(client):
    # Limiter default is 10 failures per window.
    for _ in range(10):
        client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
    blocked = client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
    assert blocked.status_code == 429
    # Even correct credentials are rejected while blocked.
    still = client.post("/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert still.status_code == 429


def test_session_stores_canonical_username_not_form_value(app):
    # Username compare is constant-time exact-match, so only the configured
    # value authenticates; the session must echo the canonical value.
    c = TestClient(app, follow_redirects=False)
    c.post("/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    page = c.get("/")
    assert TEST_USERNAME in page.text


def test_secret_key_minimum_length_enforced():
    env = {"APP_USERNAME": "u", "APP_PASSWORD": "p", "APP_SECRET_KEY": "too-short"}
    with pytest.raises(RuntimeError, match="32 characters"):
        Settings.from_env(env)


def test_https_only_parsed_from_env():
    base = {
        "APP_USERNAME": "u",
        "APP_PASSWORD": "p",
        "APP_SECRET_KEY": "x" * 32,
    }
    assert Settings.from_env(base).https_only is False
    assert Settings.from_env({**base, "APP_HTTPS_ONLY": "true"}).https_only is True
