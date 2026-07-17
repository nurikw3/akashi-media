"""Auth + scaffold acceptance: main page renders only behind the shared login."""

from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_index_redirects_when_anonymous(client):
    resp = client.get("/")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "AkashiMedia" in resp.text


def test_login_success_sets_session_and_redirects(client):
    resp = client.post("/login", data={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_failure_returns_401(client):
    resp = client.post("/login", data={"username": TEST_USERNAME, "password": "wrong"})
    assert resp.status_code == 401
    assert "Неверный" in resp.text


def test_index_renders_after_login(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert "Композер" in resp.text or "composer" in resp.text
    # Composer surfaces both channel actions.
    assert "Instagram" in resp.text
    assert "LinkedIn" in resp.text


def test_digest_dashboard_is_login_protected_and_renders_stats(auth_client, client):
    assert client.get("/digest").status_code == 303

    response = auth_client.get("/digest")

    assert response.status_code == 200
    assert "Дайджест" in response.text
    assert "Опубликовано" in response.text


def test_logout_clears_session(auth_client):
    logout = auth_client.post("/logout")
    assert logout.status_code == 303
    # After logout the protected page redirects again.
    after = auth_client.get("/")
    assert after.status_code == 303
    assert after.headers["location"] == "/login"
