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


def test_delete_case_removes_case_and_children(client, auth_log_bytes):
    created = client.post("/api/cases", json={"title": "Case To Delete"}).json()
    case_id = created["id"]

    uploaded = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("auth.log", auth_log_bytes, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    parsed = client.post(
        f"/api/evidence/{evidence['id']}/parse", params={"case_id": case_id}
    )
    assert parsed.status_code == 200, parsed.text

    # A report so the deletion has to clean generated artefacts too.
    report = client.post(f"/api/cases/{case_id}/reports", json={"report_type": "json"})
    assert report.status_code == 201, report.text

    deleted = client.delete(f"/api/cases/{case_id}")
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["deleted"] is True
    assert body["case_id"] == case_id
    assert body["removed"]["evidence"] == 1

    # The case and everything scoped to it are gone.
    assert client.get(f"/api/cases/{case_id}").status_code == 404
    assert client.get(f"/api/cases/{case_id}/evidence").status_code == 404
    assert client.get(f"/api/cases/{case_id}/reports").status_code == 404
    assert client.get(f"/api/evidence/{evidence['id']}", params={"case_id": case_id}).status_code == 404

    listed = client.get("/api/cases").json()
    assert all(item["id"] != case_id for item in listed)


def test_shared_demo_templates_cannot_be_deleted(client, db):
    """The seeded demo cases are recreated on restart; deleting them would only
    make the demo inconsistent until the next boot."""
    from app.models import Case
    from app.services.demo_seed_service import DEMO_TEMPLATE_TITLES

    # A real demo template: is_demo with no owner, like the seeded ones.
    template = Case(
        title=sorted(DEMO_TEMPLATE_TITLES)[0],
        description="seeded template",
        is_demo=True,
        owner_id=None,
    )
    db.add(template)
    db.commit()

    response = client.delete(f"/api/cases/{template.id}")
    assert response.status_code == 403
    assert "demo" in response.json()["detail"].lower()

    # Still present.
    assert client.get(f"/api/cases/{template.id}").status_code == 200


def test_demo_session_case_with_custom_title_can_be_deleted(client, db):
    """A case a visitor created inside the demo workspace is theirs to remove.
    This is the case that was previously undeletable: ownerless and not seeded."""
    from app.models import Case

    created = Case(
        title="operation red ledger",
        description="visitor created",
        is_demo=True,
        owner_id=None,
    )
    db.add(created)
    db.commit()

    response = client.delete(f"/api/cases/{created.id}")
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True
    assert client.get(f"/api/cases/{created.id}").status_code == 404


def test_deleting_missing_case_returns_404(client):
    response = client.delete("/api/cases/does-not-exist")
    assert response.status_code == 404
