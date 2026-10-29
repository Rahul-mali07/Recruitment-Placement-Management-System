"""Candidate queries and persistence."""

from __future__ import annotations

import sqlite3

from db import get_db, log_activity
from services import ServiceError


def _next_code(db) -> str:
    row = db.execute(
        "SELECT MAX(CAST(SUBSTR(candidate_code, 4) AS INTEGER)) AS max_id FROM candidates "
        "WHERE candidate_code LIKE 'CAN%'"
    ).fetchone()
    number = (row["max_id"] or 1000) + 1
    return f"CAN{number}"


def list_candidates(filters: dict, page: int = 1, per_page: int = 10) -> dict:
    clauses: list[str] = []
    params: list = []
    if filters.get("candidate_id"):
        clauses.append("candidate_code LIKE ?")
        params.append(f"%{filters['candidate_id']}%")
    if filters.get("name"):
        clauses.append("full_name LIKE ?")
        params.append(f"%{filters['name']}%")
    if filters.get("mobile"):
        clauses.append("mobile LIKE ?")
        params.append(f"%{filters['mobile']}%")
    if filters.get("email"):
        clauses.append("email LIKE ?")
        params.append(f"%{filters['email']}%")
    if filters.get("technology"):
        clauses.append("primary_technology = ?")
        params.append(filters["technology"])
    if filters.get("passing_year"):
        clauses.append("passing_year = ?")
        params.append(filters["passing_year"])
    if filters.get("qualification"):
        clauses.append("qualification = ?")
        params.append(filters["qualification"])
    if filters.get("status"):
        clauses.append("profile_status = ?")
        params.append(filters["status"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) AS count FROM candidates {where}", params).fetchone()["count"]
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), pages)
    offset = (page - 1) * per_page
    items = db.execute(
        f"SELECT * FROM candidates {where} ORDER BY candidate_code LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ).fetchall()
    return {
        "items": [dict(row) for row in items],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
    }


def get_candidate(candidate_id: int):
    row = get_db().execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    return dict(row) if row else None


def get_by_email(email: str, exclude_id: int | None = None):
    if exclude_id:
        row = get_db().execute(
            "SELECT * FROM candidates WHERE email = ? COLLATE NOCASE AND id <> ?",
            (email, exclude_id),
        ).fetchone()
    else:
        row = get_db().execute(
            "SELECT * FROM candidates WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
    return dict(row) if row else None


def list_candidates_for_select() -> list[dict]:
    rows = get_db().execute(
        "SELECT id, candidate_code, full_name, primary_technology FROM candidates "
        "ORDER BY full_name"
    ).fetchall()
    return [dict(row) for row in rows]


def create_candidate(data: dict, user_id: int | None = None) -> int:
    db = get_db()
    if get_by_email(data["email"]):
        raise ServiceError("A candidate with this email address already exists.",
                           {"email": "This email address is already registered."})
    code = _next_code(db)
    try:
        cursor = db.execute(
            """INSERT INTO candidates (
                candidate_code, full_name, email, mobile, date_of_birth, gender,
                qualification, college, university, passing_year, score, score_type,
                backlog_count, primary_technology, secondary_skills, skill_level,
                current_location, preferred_location, profile_status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code, data["full_name"], data["email"], data["mobile"],
                data.get("date_of_birth") or None, data.get("gender") or None,
                data["qualification"], data["college"], data.get("university") or None,
                data["passing_year"], data["score"], data.get("score_type", "PERCENTAGE"),
                data["backlog_count"], data["primary_technology"],
                data.get("secondary_skills") or None, data["skill_level"],
                data.get("current_location") or None, data.get("preferred_location") or None,
                data["profile_status"], user_id,
            ),
        )
        log_activity("Candidate created", "candidate", cursor.lastrowid,
                     f"{code} - {data['full_name']}", user_id)
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The candidate could not be saved because a unique value is duplicated.") from exc


def update_candidate(candidate_id: int, data: dict, user_id: int | None = None) -> None:
    db = get_db()
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise ServiceError("Candidate not found.")
    duplicate = get_by_email(data["email"], exclude_id=candidate_id)
    if duplicate:
        raise ServiceError("A candidate with this email address already exists.",
                           {"email": "This email address is already registered."})
    try:
        db.execute(
            """UPDATE candidates SET
                full_name = ?, email = ?, mobile = ?, date_of_birth = ?, gender = ?,
                qualification = ?, college = ?, university = ?, passing_year = ?,
                score = ?, score_type = ?, backlog_count = ?, primary_technology = ?,
                secondary_skills = ?, skill_level = ?, current_location = ?,
                preferred_location = ?, profile_status = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (
                data["full_name"], data["email"], data["mobile"],
                data.get("date_of_birth") or None, data.get("gender") or None,
                data["qualification"], data["college"], data.get("university") or None,
                data["passing_year"], data["score"], data.get("score_type", "PERCENTAGE"),
                data["backlog_count"], data["primary_technology"],
                data.get("secondary_skills") or None, data["skill_level"],
                data.get("current_location") or None, data.get("preferred_location") or None,
                data["profile_status"], candidate_id,
            ),
        )
        log_activity("Candidate updated", "candidate", candidate_id,
                     f"{candidate['candidate_code']} - {data['full_name']}", user_id)
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The candidate could not be updated because a unique value is duplicated.") from exc


def candidate_profile(candidate_id: int) -> dict | None:
    db = get_db()
    candidate = get_candidate(candidate_id)
    if not candidate:
        return None
    applications = db.execute(
        """SELECT a.*, j.job_code, j.title AS job_title, j.technology,
                  co.name AS company_name, o.offer_status, o.joining_status
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN companies co ON co.id = j.company_id
           LEFT JOIN offers o ON o.application_id = a.id
           WHERE a.candidate_id = ?
           ORDER BY a.applied_date DESC, a.id DESC""",
        (candidate_id,),
    ).fetchall()
    interviews = db.execute(
        """SELECT i.*, j.job_code, j.title AS job_title, co.name AS company_name,
                  f.interview_result
           FROM interviews i
           JOIN jobs j ON j.id = i.job_id
           JOIN companies co ON co.id = i.company_id
           LEFT JOIN interview_feedback f ON f.interview_id = i.id
           WHERE i.candidate_id = ?
           ORDER BY i.interview_date DESC, i.interview_time DESC""",
        (candidate_id,),
    ).fetchall()
    offers = db.execute(
        """SELECT o.*, a.application_code, j.job_code, j.title AS job_title,
                  co.name AS company_name
           FROM offers o
           JOIN applications a ON a.id = o.application_id
           JOIN jobs j ON j.id = a.job_id
           JOIN companies co ON co.id = j.company_id
           WHERE a.candidate_id = ?
           ORDER BY o.offer_date DESC, o.id DESC""",
        (candidate_id,),
    ).fetchall()
    return {
        "candidate": candidate,
        "applications": [dict(row) for row in applications],
        "interviews": [dict(row) for row in interviews],
        "offers": [dict(row) for row in offers],
        "application_count": len(applications),
        "offer_count": len(offers),
    }
