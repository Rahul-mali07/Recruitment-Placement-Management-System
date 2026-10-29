"""Authentication, CSRF and role authorization tests."""

from __future__ import annotations

import re

from werkzeug.security import generate_password_hash

from app import create_app
from config import TestConfig
from db import get_db, init_db
from seed import seed_demo
from utils.auth import safe_next_url


def test_login_required_redirects_to_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert "next=" in response.headers["Location"]
    assert "dashboard" in response.headers["Location"]


def test_login_success_and_logout(client, login):
    login("ADMIN")
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"System Administrator" in dashboard.data
    assert b"Admin" in dashboard.data

    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert client.get("/dashboard").status_code == 302


def test_login_rejects_wrong_password_and_role(client):
    wrong = client.post(
        "/login",
        data={"identifier": "admin", "password": "wrong-password", "role": "ADMIN"},
    )
    assert wrong.status_code == 200
    assert b"Invalid username/email or password" in wrong.data

    wrong_role = client.post(
        "/login",
        data={"identifier": "recruiter", "password": "Recruiter@12345", "role": "ADMIN"},
    )
    assert wrong_role.status_code == 200
    assert b"selected role does not match" in wrong_role.data


def test_inactive_user_cannot_login(app, client):
    with app.app_context():
        get_db().execute(
            "INSERT INTO users (username, email, full_name, password_hash, role, is_active) "
            "VALUES (?, ?, ?, ?, 'RECRUITER', 0)",
            (
                "disabled",
                "disabled@example.com",
                "Disabled User",
                generate_password_hash("Disabled@12345"),
            ),
        )
        get_db().commit()
    response = client.post(
        "/login",
        data={"identifier": "disabled", "password": "Disabled@12345", "role": "RECRUITER"},
    )
    assert response.status_code == 200
    assert b"account is inactive" in response.data


def test_role_permissions(client, login):
    login("RECRUITER")
    assert client.get("/candidates").status_code == 200
    assert client.get("/companies").status_code == 200
    assert client.get("/jobs").status_code == 200
    denied = client.get("/reports")
    assert denied.status_code == 302
    assert denied.headers["Location"].endswith("/access-denied")
    assert client.get("/access-denied").status_code == 403
    client.post("/logout")

    login("PLACEMENT_OFFICER")
    assert client.get("/reports").status_code == 200
    assert client.get("/applications").status_code == 200
    assert client.get("/jobs").status_code == 302
    assert client.get("/companies").status_code == 302


def test_csrf_token_is_enforced(tmp_path):
    app = create_app(
        TestConfig,
        {
            "DATABASE": str(tmp_path / "csrf.db"),
            "SECRET_KEY": "csrf-test-key",
            "CSRF_ENABLED": True,
            "TESTING": True,
        },
    )
    with app.app_context():
        init_db()
        seed_demo()
    client = app.test_client()

    page = client.get("/login")
    token_match = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    assert token_match
    token = token_match.group(1)

    missing = client.post(
        "/login",
        data={"identifier": "admin", "password": "Admin@12345", "role": "ADMIN"},
    )
    assert missing.status_code == 400
    assert b"security token" in missing.data or b"session token" in missing.data

    accepted = client.post(
        "/login",
        data={
            "identifier": "admin",
            "password": "Admin@12345",
            "role": "ADMIN",
            "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert accepted.status_code == 302
    assert accepted.headers["Location"].endswith("/dashboard")


def test_safe_next_url_blocks_external_targets():
    assert safe_next_url("/reports?technology=Python") == "/reports?technology=Python"
    assert safe_next_url("https://evil.example/phish") is None
    assert safe_next_url("//evil.example/phish") is None
    assert safe_next_url("reports") is None
    assert safe_next_url(None) is None
