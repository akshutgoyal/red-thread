def test_create_list_get_and_update_case(client):
    created = client.post(
        "/api/cases",
        json={"title": "Case Alpha", "description": "A test case"},
    )
    assert created.status_code == 201
    case = created.json()
    assert case["title"] == "Case Alpha"
    assert case["status"] == "open"

    listed = client.get("/api/cases")
    assert listed.status_code == 200
    assert any(item["id"] == case["id"] for item in listed.json())

    fetched = client.get(f"/api/cases/{case['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["evidence_count"] == 0

    updated = client.patch(
        f"/api/cases/{case['id']}",
        json={"status": "in_review", "investigator_notes": "Reviewing."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_review"

    audit = client.get(f"/api/cases/{case['id']}/audit")
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()}
    assert "case.created" in actions
    assert "case.updated" in actions


def test_rejects_empty_title(client):
    response = client.post("/api/cases", json={"title": ""})
    assert response.status_code == 422


def test_missing_case_returns_404(client):
    response = client.get("/api/cases/does-not-exist")
    assert response.status_code == 404
