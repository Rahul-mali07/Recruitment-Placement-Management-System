"""Shared pytest fixtures for the Kiran Academy placement system."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from db import get_db, init_db  # noqa: E402
from seed import seed_demo  # noqa: E402

CREDENTIALS = {
    "ADMIN": ("admin", "Admin@12345"),
    "RECRUITER": ("recruiter", "Recruiter@12345"),
    "PLACEMENT_OFFICER": ("placement", "Placement@12345"),
}


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        TestConfig,
        {
            "DATABASE": str(tmp_path / "test-recruitment.db"),
            "SECRET_KEY": "test-secret-key",
            "CSRF_ENABLED": False,
            "TESTING": True,
        },
    )
    with app.app_context():
        init_db()
        seed_demo()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login(client):
    def _login(role: str = "ADMIN"):
        username, password = CREDENTIALS[role]
        response = client.post(
            "/login",
            data={"identifier": username, "password": password, "role": role},
            follow_redirects=False,
        )
        assert response.status_code == 302, response.get_data(as_text=True)
        assert response.headers["Location"].endswith("/dashboard")
        return response

    return _login


def fetchone(app, sql: str, params=()):
    with app.app_context():
        row = get_db().execute(sql, params).fetchone()
        return dict(row) if row else None


def fetchall(app, sql: str, params=()):
    with app.app_context():
        return [dict(row) for row in get_db().execute(sql, params).fetchall()]


def scalar(app, sql: str, params=()):
    with app.app_context():
        row = get_db().execute(sql, params).fetchone()
        return row[0] if row else None


def id_for(app, table: str, column: str, value):
    row = fetchone(app, f"SELECT id FROM {table} WHERE {column} = ?", (value,))
    assert row, f"{table}.{column}={value!r} not found"
    return row["id"]
