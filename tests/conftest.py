"""Shared test fixtures. Tests never touch real env or real external APIs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, create_app

TEST_USERNAME = "marketing"
TEST_PASSWORD = "s3cret-pass"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        secret_key="test-secret-key-not-for-production-0123456789",
        https_only=False,
        openai_api_key=None,
        openai_model="gpt-4o-mini",
        ig_token=None,
        ig_user_id=None,
        li_token=None,
        li_author_urn=None,
    )


@pytest.fixture
def app(settings: Settings):
    return create_app(settings=settings)


@pytest.fixture
def client(app) -> TestClient:
    # Do not follow redirects automatically — auth flow asserts on 303s.
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def auth_client(app) -> TestClient:
    c = TestClient(app, follow_redirects=False)
    resp = c.post("/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert resp.status_code == 303
    return c
