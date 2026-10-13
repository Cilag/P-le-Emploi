"""
Security tests for GUI-161:
- SEC-01: all protected routes return 401 without token
- SEC-02: /cv/audit rejects non-user email when user_email is configured
- JWT token issuance and round-trip
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.auth import create_access_token, get_password_hash


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_headers():
    token = create_access_token(settings.api_username)
    return {"Authorization": f"Bearer {token}"}


# ── SEC-01: unauthenticated requests return 401 ──────────────────────────────

PROTECTED_ROUTES = [
    ("GET",  "/offres"),
    ("GET",  "/lettres"),
    ("GET",  "/candidatures"),
    ("GET",  "/cv"),
    ("GET",  "/api/scheduler/cv-audit"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_protected_routes_require_auth(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401, (
        f"{method} {path} should return 401 without token, got {response.status_code}"
    )


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_auth_token_endpoint_is_public(client):
    """Login endpoint must be reachable without a token."""
    response = client.post("/auth/token", data={"username": "x", "password": "wrong"})
    assert response.status_code == 401  # wrong creds, not 403/404


# ── JWT issuance ─────────────────────────────────────────────────────────────

def test_login_wrong_password(client):
    response = client.post(
        "/auth/token",
        data={"username": settings.api_username, "password": "definitely_wrong"},
    )
    assert response.status_code == 401


def test_login_correct_credentials(client, monkeypatch):
    hashed = get_password_hash("correct_password")
    monkeypatch.setattr(settings, "api_password_hash", hashed)

    response = client.post(
        "/auth/token",
        data={"username": settings.api_username, "password": "correct_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_invalid_token_rejected(client):
    response = client.get("/offres", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


# ── SEC-02: CV audit email guard ─────────────────────────────────────────────

def test_audit_rejects_non_user_email(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "user_email", "user@example.com")
    response = client.post(
        "/cv/audit",
        json={"email_destination": "attacker@evil.com", "jour_execution": 1},
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_audit_allows_user_email(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "user_email", "user@example.com")
    with patch("app.workers_client.run_cv_audit_task") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id="abc123")
        response = client.post(
            "/cv/audit",
            json={"email_destination": "user@example.com", "jour_execution": 1},
            headers=auth_headers,
        )
    assert response.status_code == 202


def test_audit_no_restriction_when_user_email_unset(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "user_email", "")
    with patch("app.workers_client.run_cv_audit_task") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id="abc123")
        response = client.post(
            "/cv/audit",
            json={"email_destination": "anyone@example.com", "jour_execution": 1},
            headers=auth_headers,
        )
    assert response.status_code == 202
