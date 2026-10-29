"""SQLite helpers shared by the Flask app and the service layer."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return a request-scoped connection with foreign keys enforced."""
    if "db" not in g:
        database = Path(current_app.config["DATABASE"])
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    """Create all tables and indexes from schema.sql."""
    connection = get_db()
    schema_path = Path(current_app.root_path) / "schema.sql"
    with schema_path.open("r", encoding="utf-8") as handle:
        connection.executescript(handle.read())
    connection.commit()


@contextmanager
def transaction():
    """Explicit transaction for multi-table changes."""
    connection = get_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def log_activity(action: str, entity_type: str, entity_id: int | None = None,
                 details: str | None = None, user_id: int | None = None) -> None:
    """Append an audit-friendly activity entry (participates in caller commit)."""
    if user_id is None:
        user = g.get("user")
        user_id = user["id"] if user else None
    get_db().execute(
        "INSERT INTO activity_log (user_id, action, entity_type, entity_id, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, action, entity_type, entity_id, details),
    )


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
