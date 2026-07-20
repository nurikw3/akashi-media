def test_ai_content_generation_requires_login(client):
    response = client.post("/content/generate", data={"task": "generate_ideas", "brief": "AI"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_ai_content_generation_returns_editable_result(auth_client):
    response = auth_client.post(
        "/content/generate", data={"task": "generate_ideas", "brief": "Темы про AI"}
    )
    assert response.status_code == 200
    assert 'id="ai-content-result"' in response.text
    assert 'id="ai-generated-text"' in response.text
    assert "generate_ideas" in response.text


def test_ai_content_generation_rejects_unknown_task(auth_client):
    response = auth_client.post(
        "/content/generate", data={"task": "unknown", "brief": "Темы про AI"}
    )
    assert response.status_code == 200
    assert "alert--error" in response.text
