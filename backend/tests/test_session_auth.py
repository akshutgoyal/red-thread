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
