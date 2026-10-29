"""Authorization helpers and navigation metadata."""

from __future__ import annotations

from functools import wraps
from urllib.parse import urlsplit

from flask import flash, g, redirect, request, session, url_for

ROLE_LABELS = {
    "ADMIN": "Admin",
    "RECRUITER": "Recruiter",
    "PLACEMENT_OFFICER": "Placement Officer",
}

NAV_ITEMS = [
    ("dashboard", "Dashboard", "dashboard"),
    ("candidates", "Candidates", "candidates"),
    ("companies", "Companies", "companies"),
    ("jobs", "Jobs", "jobs"),
    ("applications", "Applications", "applications"),
    ("interviews", "Interviews", "interviews"),
    ("placement", "Placement Process", "placement_process"),
    ("reports", "Reports", "reports"),
]

ROLE_PERMISSIONS = {
    "ADMIN": {"dashboard", "candidates", "companies", "jobs", "applications",
              "interviews", "placement", "reports"},
    "RECRUITER": {"dashboard", "candidates", "companies", "jobs", "applications",
                  "interviews", "placement"},
    "PLACEMENT_OFFICER": {"dashboard", "candidates", "applications", "interviews",
                          "placement", "reports"},
}


def current_role() -> str | None:
    return session.get("user_role")


def user_can(module: str) -> bool:
    role = current_role()
    return bool(role and module in ROLE_PERMISSIONS.get(role, set()))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or not getattr(g, "user", None):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id") or not getattr(g, "user", None):
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            if session.get("user_role") not in roles:
                flash("You do not have permission to access that area.", "error")
                return redirect(url_for("access_denied"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def module_required(module: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id") or not getattr(g, "user", None):
                flash("Please sign in to continue.", "warning")
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
            if not user_can(module):
                flash("You do not have permission to access that area.", "error")
                return redirect(url_for("access_denied"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def safe_next_url(target: str | None) -> str | None:
    """Only allow local absolute paths to prevent open redirects."""
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target
