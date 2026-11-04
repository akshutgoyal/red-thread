from __future__ import annotations

from app.services.auth_service import (
    AuthPrincipal,
    create_session_token,
    decode_session_token,
)


def _headers(principal: AuthPrincipal) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_session_token(principal)}"}


def test_session_token_round_trip():
    principal = AuthPrincipal(
        user_id="user-test", email="test@example.com", name="Test User"
    )
    token = create_session_token(principal)
    decoded = decode_session_token(token)
    assert decoded == principal


def test_demo_login_and_me(client):
    response = client.post("/api/auth/demo")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["is_demo"] is True
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["is_demo"] is True


def test_personal_cases_are_scoped_and_cross_account_access_is_denied(client):
    owner = AuthPrincipal(user_id="user-owner", email="owner@example.com", name="Owner")
    stranger = AuthPrincipal(user_id="user-stranger", email="other@example.com", name="Other")
    created = client.post(
        "/api/cases",
        headers=_headers(owner),
        json={"title": "Owner private case", "description": "Private test case."},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    owner_list = client.get("/api/cases", headers=_headers(owner))
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()] == [case_id]

    stranger_list = client.get("/api/cases", headers=_headers(stranger))
    assert stranger_list.status_code == 200
    assert case_id not in [item["id"] for item in stranger_list.json()]

    denied = client.get(f"/api/cases/{case_id}", headers=_headers(stranger))
    assert denied.status_code == 403, denied.text

    allowed = client.get(f"/api/cases/{case_id}", headers=_headers(owner))
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["is_demo"] is False


def test_demo_scope_only_returns_demo_cases(client):
    demo = client.post("/api/auth/demo")
    assert demo.status_code == 200
    headers = {"Authorization": f"Bearer {demo.json()['token']}"}
    response = client.get("/api/cases", headers=headers)
    assert response.status_code == 200
    assert all(item["is_demo"] for item in response.json())


def test_google_login_creates_a_new_empty_workspace(client, monkeypatch):
    claims = {
        "sub": "google-sub-new-user",
        "email": "new-google@example.com",
        "email_verified": True,
        "name": "New Google Investigator",
    }
    monkeypatch.setattr(
        "app.api.auth.verify_google_credential",
        lambda _credential: claims,
    )
    response = client.post(
        "/api/auth/google",
        json={"credential": "test-google-credential"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["email"] == "new-google@example.com"
    assert payload["user"]["is_demo"] is False
    cases = client.get(
        "/api/cases",
        headers={"Authorization": f"Bearer {payload['token']}"},
    )
    assert cases.status_code == 200
    assert cases.json() == []


def test_demo_session_uses_httponly_cookie(client):
    client.cookies.clear()
    response = client.post("/api/auth/demo")
    assert response.status_code == 200
    cookie = response.headers.get("set-cookie", "").lower()
    assert "red_thread_session=" in cookie
    assert "httponly" in cookie
    assert "samesite" in cookie

    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["is_demo"] is True

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_demo_cases_are_copied_per_visitor(client, db):
    from app.schemas.case import CaseCreate
    from app.services import case_service

    template = case_service.create_case(
        db,
        CaseCreate(title="Per Visitor Demo Template", description="Synthetic template."),
        is_demo=True,
    )
    assert template.owner_id is None

    client.cookies.clear()
    first = client.post("/api/auth/demo")
    assert first.status_code == 200, first.text
    first_token = first.json()["token"]
    first_headers = {"Authorization": f"Bearer {first_token}"}
    first_cases = client.get("/api/cases", headers=first_headers).json()
    first_copy = next(item for item in first_cases if item["title"] == template.title)
    assert first_copy["id"] != template.id
    assert first_copy["is_demo"] is True

    client.cookies.clear()
    second = client.post("/api/auth/demo")
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] != first.json()["user"]["id"]
    second_headers = {"Authorization": f"Bearer {second.json()['token']}"}
    second_cases = client.get("/api/cases", headers=second_headers).json()
    second_ids = {item["id"] for item in second_cases}
    assert first_copy["id"] not in second_ids
    assert any(item["title"] == template.title for item in second_cases)
