def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["app"] == "Red Thread"
    assert payload["ai_provider"] in {"commandcode", "tokenharbor", "none"}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Red Thread"
