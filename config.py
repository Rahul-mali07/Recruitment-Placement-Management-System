"""Application configuration.

Secrets and environment-specific values are read from environment variables.
A `.env` file next to this module is loaded when present (simple KEY=VALUE
parser using the standard library only).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding real environment values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"


class Config:
    APP_ENV = APP_ENV
    IS_PRODUCTION = IS_PRODUCTION

    # In production a real SECRET_KEY is mandatory. In local development an
    # ephemeral key is generated so sessions reset whenever the server restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY") or (None if IS_PRODUCTION else secrets.token_hex(32))

    DATABASE = os.environ.get(
        "DATABASE_PATH",
        str(Path(os.environ.get("INSTANCE_PATH", BASE_DIR / "instance")) / "recruitment.db"),
    )

    CSRF_ENABLED = _as_bool(os.environ.get("CSRF_ENABLED"), True)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), IS_PRODUCTION)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # eight hours

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    JSON_SORT_KEYS = False


class TestConfig(Config):
    APP_ENV = "testing"
    IS_PRODUCTION = False
    SECRET_KEY = "test-secret-key"
    CSRF_ENABLED = False
    TESTING = True
