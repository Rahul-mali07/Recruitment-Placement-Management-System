"""Interview scheduling and result tracking."""

from __future__ import annotations

from datetime import date

from db import get_db, log_activity
from services import ServiceError

BASE_SELECT = """
    SELECT i.*, a.application_code, a.status AS application_status,
           c.full_name AS candidate_name, c.candidate_code, c.primary_technology,
           j.job_code, j.title AS job_title, co.name AS company_name,
           f.interview_result, f.overall_rating, f.remarks
    FROM interviews i
    JOIN applications a ON a.id = i.application_id
    JOIN candidates c ON c.id = i.candidate_id
    JOIN jobs j ON j.id = i.job_id
    JOIN companies co ON co.id = i.company_id
    LEFT JOIN interview_feedback f ON f.interview_id = i.id
"""


def _next_code(db) -> str:
    row = db.execute(
        "SELECT MAX(CAST(SUBSTR(interview_code, 4) AS INTEGER)) AS max_id "
        "FROM interviews WHERE interview_code LIKE 'INT%'"
    ).fetchone()
    number = (row["max_id"] or 1000) + 1
    return f"INT{number}"


def list_interviews(filters: dict) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if filters.get("q"):
        term = f"%{filters['q']}%"
        clauses.append("(c.full_name LIKE ? OR co.name LIKE ? OR j.title LIKE ? OR i.interview_code LIKE ?)")
        params.extend([term, term, term, term])
    if filters.get("status"):
        clauses.append("i.status = ?")
        params.append(filters["status"])
    if filters.get("date_from"):
        clauses.append("i.interview_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("i.interview_date <= ?")
        params.append(filters["date_to"])
    if filters.get("candidate_id"):
        clauses.append("i.candidate_id = ?")
        params.append(filters["candidate_id"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = get_db().execute(
        f"{BASE_SELECT} {where} ORDER BY i.interview_date DESC, i.interview_time DESC, i.id DESC",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def get_interview(interview_id: int):
    row = get_db().execute(f"{BASE_SELECT} WHERE i.id = ?", (interview_id,)).fetchone()
    return dict(row) if row else None


def today_interviews() -> list[dict]:
    rows = get_db().execute(
        f"{BASE_SELECT} WHERE i.interview_date = ? AND i.status IN ('SCHEDULED', 'RESCHEDULED') "
        "ORDER BY i.interview_time",
        (date.today().isoformat(),),
    ).fetchall()
    return [dict(row) for row in rows]


def upcoming_interviews(limit: int = 6) -> list[dict]:
    rows = get_db().execute(
        f"{BASE_SELECT} WHERE i.interview_date > ? AND i.status IN ('SCHEDULED', 'RESCHEDULED') "
        "ORDER BY i.interview_date, i.interview_time LIMIT ?",
        (date.today().isoformat(), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def list_for_application(application_id: int) -> list[dict]:
    rows = get_db().execute(
        f"{BASE_SELECT} WHERE i.application_id = ? "
        "ORDER BY i.interview_date DESC, i.interview_time DESC",
        (application_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _resolve_application(candidate_id: int, company_id: int, job_id: int) -> dict:
    db = get_db()
    row = db.execute(
        """SELECT a.*, j.company_id, j.status AS job_status, co.status AS company_status
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN companies co ON co.id = j.company_id
           WHERE a.candidate_id = ? AND a.job_id = ?""",
        (candidate_id, job_id),
    ).fetchone()
    if not row:
        raise ServiceError(
            "No application exists for this candidate and job. Create the application first."
        )
    if row["company_id"] != company_id:
        raise ServiceError("The selected company does not match the job opening's company.")
    if row["status"] in {"REJECTED", "WITHDRAWN"}:
        raise ServiceError("An interview cannot be scheduled for a rejected or withdrawn application.")
    if row["status"] not in {"ELIGIBLE", "SHORTLISTED", "INTERVIEW_SCHEDULED"}:
        raise ServiceError(
            "The application must be eligible or shortlisted before an interview is scheduled."
        )
    return dict(row)


def schedule(data: dict) -> int:
    app = _resolve_application(data["candidate_id"], data["company_id"], data["job_id"])
    db = get_db()
    code = _next_code(db)
    cursor = db.execute(
        """INSERT INTO interviews (interview_code, application_id, candidate_id, job_id,
               company_id, round, interview_date, interview_time, mode,
               interviewer_name, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SCHEDULED')""",
        (
            code, app["id"], data["candidate_id"], data["job_id"], data["company_id"],
            data["round"], data["interview_date"], data["interview_time"],
            data["mode"], data.get("interviewer_name") or None,
        ),
    )
    db.execute(
        """UPDATE applications SET status = 'INTERVIEW_SCHEDULED', updated_at = datetime('now')
           WHERE id = ? AND status IN ('ELIGIBLE', 'SHORTLISTED')""",
        (app["id"],),
    )
    log_activity("Interview scheduled", "interview", cursor.lastrowid,
                 f"{code} for {app['application_code']}")
    db.commit()
    return cursor.lastrowid


def reschedule(interview_id: int, data: dict) -> None:
    interview = get_interview(interview_id)
    if not interview:
        raise ServiceError("Interview not found.")
    if interview["status"] not in {"SCHEDULED", "RESCHEDULED"}:
        raise ServiceError("Only scheduled or rescheduled interviews can be rescheduled.")
    db = get_db()
    db.execute(
        """UPDATE interviews SET round = ?, interview_date = ?, interview_time = ?,
               mode = ?, interviewer_name = ?, status = 'RESCHEDULED',
               updated_at = datetime('now')
           WHERE id = ?""",
        (
            data["round"], data["interview_date"], data["interview_time"], data["mode"],
            data.get("interviewer_name") or None, interview_id,
        ),
    )
    db.execute(
        """UPDATE applications SET status = 'INTERVIEW_SCHEDULED', updated_at = datetime('now')
           WHERE id = ? AND status IN ('ELIGIBLE', 'SHORTLISTED')""",
        (interview["application_id"],),
    )
    log_activity("Interview rescheduled", "interview", interview_id,
                 f"{interview['interview_code']} moved to {data['interview_date']} {data['interview_time']}")
    db.commit()


def mark_no_show(interview_id: int) -> None:
    interview = get_interview(interview_id)
    if not interview:
        raise ServiceError("Interview not found.")
    if interview["status"] not in {"SCHEDULED", "RESCHEDULED"}:
        raise ServiceError("Only scheduled or rescheduled interviews can be marked as no show.")
    db = get_db()
    db.execute(
        "UPDATE interviews SET status = 'NO_SHOW', updated_at = datetime('now') WHERE id = ?",
        (interview_id,),
    )
    log_activity("Interview marked no show", "interview", interview_id, interview["interview_code"])
    db.commit()


def mark_completed(interview_id: int) -> None:
    db = get_db()
    db.execute(
        "UPDATE interviews SET status = 'COMPLETED', updated_at = datetime('now') WHERE id = ?",
        (interview_id,),
    )
