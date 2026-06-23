"""HTTP slice: POST /repackage/linkedin returns an editable adapted-text fragment."""


def test_repackage_requires_login(client):
    resp = client.post("/repackage/linkedin", data={"source_text": "hi"})
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_repackage_returns_editable_fragment(auth_client):
    resp = auth_client.post("/repackage/linkedin", data={"source_text": "Запуск 🚀"})
    assert resp.status_code == 200
    # Fragment must re-render the swap target and an editable field.
    assert 'id="linkedin-adapted"' in resp.text
    assert "<textarea" in resp.text
    assert 'name="linkedin_text"' in resp.text
    # Fake adapter (no OPENAI_API_KEY in tests) echoes the source into a LinkedIn frame.
    assert "Запуск" in resp.text


def test_repackage_empty_text_shows_error_fragment(auth_client):
    resp = auth_client.post("/repackage/linkedin", data={"source_text": "   "})
    # htmx still swaps; surface a friendly error rather than a 4xx blank.
    assert resp.status_code == 200
    assert 'id="linkedin-adapted"' in resp.text
    assert "alert--error" in resp.text
    assert "Не удалось" in resp.text
