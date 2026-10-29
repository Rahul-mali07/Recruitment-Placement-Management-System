"""Application tracking, duplicate prevention and eligibility rules."""

from __future__ import annotations

import re
import sqlite3

from db import get_db, log_activity
from services import ServiceError

SHORTLIST_FROM = {"APPLIED", "ELIGIBLE"}
REJECT_FROM = {"APPLIED", "ELIGIBLE", "SHORTLISTED", "INTERVIEW_SCHEDULED"}

BASE_SELECT = """
    SELECT a.*, c.candidate_code, c.full_name AS candidate_name, c.email AS candidate_email,
           c.mobile AS candidate_mobile, c.primary_technology,
           c.profile_status AS candidate_status,
           j.job_code, j.title AS job_title, j.technology AS job_technology,
           j.status AS job_status, co.id AS company_id, co.name AS company_name,
           o.id AS offer_id, o.offer_status, o.joining_status,
           u.full_name AS recruiter_name
    FROM applications a
    JOIN candidates c ON c.id = a.candidate_id
    JOIN jobs j ON j.id = a.job_id
    JOIN companies co ON co.id = j.company_id
    LEFT JOIN offers o ON o.application_id = a.id
    LEFT JOIN users u ON u.id = a.recruiter_id
"""


def _filters(filters: dict) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if filters.get("application_id"):
        clauses.append("a.application_code LIKE ?")
        params.append(f"%{filters['application_id']}%")
    if filters.get("candidate"):
        clauses.append("(c.full_name LIKE ? OR c.candidate_code LIKE ?)")
        term = f"%{filters['candidate']}%"
        params.extend([term, term])
    if filters.get("company_id"):
        clauses.append("co.id = ?")
        params.append(filters["company_id"])
    if filters.get("job_id"):
        clauses.append("j.id = ?")
        params.append(filters["job_id"])
    if filters.get("status"):
        clauses.append("a.status = ?")
        params.append(filters["status"])
    if filters.get("date_from"):
        clauses.append("a.applied_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("a.applied_date <= ?")
        params.append(filters["date_to"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_applications(filters: dict) -> list[dict]:
    where, params = _filters(filters)
    rows = get_db().execute(
        f"{BASE_SELECT} {where} ORDER BY a.applied_date DESC, a.id DESC", params
    ).fetchall()
    return [dict(row) for row in rows]


def summary(filters: dict) -> dict:
    where, params = _filters(filters)
    rows = get_db().execute(
        f"""SELECT a.status, COUNT(*) AS count
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            {where} GROUP BY a.status""",
        params,
    ).fetchall()
    counts = {status: 0 for status in (
        "APPLIED", "ELIGIBLE", "SHORTLISTED", "INTERVIEW_SCHEDULED",
        "SELECTED", "REJECTED", "WITHDRAWN",
    )}
    total = 0
    for row in rows:
        counts[row["status"]] = row["count"]
        total += row["count"]
    counts["TOTAL"] = total
    return counts


def get_application(application_id: int):
    row = get_db().execute(
        f"{BASE_SELECT} WHERE a.id = ?", (application_id,)
    ).fetchone()
    return dict(row) if row else None


def get_by_candidate_job(candidate_id: int, job_id: int):
    row = get_db().execute(
        "SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?",
        (candidate_id, job_id),
    ).fetchone()
    return dict(row) if row else None


def _next_code(db) -> str:
    row = db.execute(
        "SELECT MAX(CAST(SUBSTR(application_code, 4) AS INTEGER)) AS max_id "
        "FROM applications WHERE application_code LIKE 'APP%'"
    ).fetchone()
    number = (row["max_id"] or 1000) + 1
    return f"APP{number}"


def create_application(candidate_id: int, job_id: int,
                       recruiter_id: int | None = None) -> int:
    db = get_db()
    candidate = db.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    job = db.execute(
        "SELECT j.*, c.status AS company_status FROM jobs j "
        "JOIN companies c ON c.id = j.company_id WHERE j.id = ?",
        (job_id,),
    ).fetchone()
    if not candidate:
        raise ServiceError("Select a valid candidate.")
    if not job:
        raise ServiceError("Select a valid job opening.")
    if job["status"] != "OPEN":
        raise ServiceError("Applications can only be created for open job openings.")
    if job["company_status"] != "ACTIVE":
        raise ServiceError("This company is inactive and cannot receive applications.")
    if get_by_candidate_job(candidate_id, job_id):
        raise ServiceError("Candidate has already applied for this job.")
    try:
        cursor = db.execute(
            """INSERT INTO applications (application_code, candidate_id, job_id,
                   recruiter_id, applied_date, eligibility_status, status)
               VALUES (?, ?, ?, ?, date('now'), 'NOT_CHECKED', 'APPLIED')""",
            (_next_code(db), candidate_id, job_id, recruiter_id),
        )
        log_activity("Application created", "application", cursor.lastrowid,
                     f"{candidate['full_name']} applied for {job['job_code']}")
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("Candidate has already applied for this job.") from exc


def _qualification_matches(candidate_qualification: str, job_qualifications: str) -> bool:
    required = (job_qualifications or "").lower()
    if "any" in required.split():
        return True
    tokens = [token.strip() for token in re.split(r"[,/;|]+", required) if token.strip()]
    return (candidate_qualification or "").strip().lower() in tokens


def evaluate_eligibility(candidate: dict, job: dict) -> tuple[str, str]:
    """Return (ELIGIBLE|NOT_ELIGIBLE, human readable reason)."""
    missing = []
    for field, label in (
        ("qualification", "qualification"),
        ("score", "percentage/CGPA"),
        ("passing_year", "passing year"),
        ("backlog_count", "backlog count"),
        ("primary_technology", "primary technology"),
    ):
        value = candidate.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(label)
    if missing:
        return (
            "NOT_ELIGIBLE",
            "Candidate profile is missing required information: " + ", ".join(missing) + ".",
        )

    failures: list[str] = []
    if candidate["primary_technology"].strip().lower() != (job.get("technology") or "").strip().lower():
        failures.append(
            f"technology is {candidate['primary_technology']} but the job requires {job['technology']}"
        )
    if not _qualification_matches(candidate["qualification"], job.get("qualifications", "")):
        failures.append(
            f"qualification {candidate['qualification']} is not listed in {job['qualifications']}"
        )
    if float(candidate["score"]) < float(job["min_percentage"]):
        failures.append(
            f"score {candidate['score']:g}% is below the required {job['min_percentage']:g}%"
        )
    if job.get("min_passing_year") and int(candidate["passing_year"]) < int(job["min_passing_year"]):
        failures.append(f"passing year is before {job['min_passing_year']}")
    if job.get("max_passing_year") and int(candidate["passing_year"]) > int(job["max_passing_year"]):
        failures.append(f"passing year is after {job['max_passing_year']}")
    if int(candidate["backlog_count"]) > int(job["max_backlogs"]):
        failures.append(
            f"{candidate['backlog_count']} backlogs exceed the allowed {job['max_backlogs']}"
        )

    if failures:
        return "NOT_ELIGIBLE", "Not eligible: " + "; ".join(failures) + "."
    return (
        "ELIGIBLE",
        f"Eligible: meets the {job['technology']} technology, qualification, "
        f"{job['min_percentage']:g}% score, passing year and backlog criteria.",
    )


def check_eligibility(application_id: int) -> tuple[str, str]:
    app = get_application(application_id)
    if not app:
        raise ServiceError("Application not found.")
    candidate = get_db().execute(
        "SELECT * FROM candidates WHERE id = ?", (app["candidate_id"],)
    ).fetchone()
    job = get_db().execute(
        "SELECT * FROM jobs WHERE id = ?", (app["job_id"],)
    ).fetchone()
    status, reason = evaluate_eligibility(dict(candidate), dict(job))
    db = get_db()
    new_status = app["status"]
    if status == "ELIGIBLE" and app["status"] == "APPLIED":
        new_status = "ELIGIBLE"
    db.execute(
        """UPDATE applications SET eligibility_status = ?, eligibility_reason = ?,
               status = ?, updated_at = datetime('now') WHERE id = ?""",
        (status, reason, new_status, application_id),
    )
    log_activity("Eligibility checked", "application", application_id,
                 f"{app['application_code']}: {status}")
    db.commit()
    return status, reason


def shortlist(application_id: int) -> None:
    app = get_application(application_id)
    if not app:
        raise ServiceError("Application not found.")
    if app["status"] not in SHORTLIST_FROM:
        raise ServiceError(f"An application in {app['status']} status cannot be shortlisted.")
    if app["eligibility_status"] != "ELIGIBLE":
        raise ServiceError("Check eligibility first; only eligible candidates can be shortlisted.")
    db = get_db()
    db.execute(
        "UPDATE applications SET status = 'SHORTLISTED', updated_at = datetime('now') WHERE id = ?",
        (application_id,),
    )
    log_activity("Application shortlisted", "application", application_id, app["application_code"])
    db.commit()


def reject(application_id: int) -> None:
    app = get_application(application_id)
    if not app:
        raise ServiceError("Application not found.")
    if app["status"] not in REJECT_FROM:
        raise ServiceError(f"An application in {app['status']} status cannot be rejected.")
    db = get_db()
    db.execute(
        "UPDATE applications SET status = 'REJECTED', updated_at = datetime('now') WHERE id = ?",
        (application_id,),
    )
    log_activity("Application rejected", "application", application_id, app["application_code"])
    db.commit()


def set_status(application_id: int, status: str) -> None:
    app = get_application(application_id)
    if not app:
        raise ServiceError("Application not found.")
    db = get_db()
    db.execute(
        "UPDATE applications SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, application_id),
    )
    db.commit()


def history(application_id: int) -> dict | None:
    app = get_application(application_id)
    if not app:
        return None
    db = get_db()
    interviews = db.execute(
        """SELECT i.*, f.interview_result, f.overall_rating, f.remarks
           FROM interviews i LEFT JOIN interview_feedback f ON f.interview_id = i.id
           WHERE i.application_id = ?
           ORDER BY i.interview_date DESC, i.interview_time DESC""",
        (application_id,),
    ).fetchall()
    offer = db.execute(
        "SELECT * FROM offers WHERE application_id = ?", (application_id,)
    ).fetchone()
    return {
        "application": app,
        "interviews": [dict(row) for row in interviews],
        "offer": dict(offer) if offer else None,
    }


def selected_for_placement() -> list[dict]:
    rows = get_db().execute(
        """SELECT a.id, a.application_code, c.full_name AS candidate_name,
                  j.job_code, j.title AS job_title, co.name AS company_name,
                  o.id AS offer_id, o.offer_status, o.joining_status
           FROM applications a
           JOIN candidates c ON c.id = a.candidate_id
           JOIN jobs j ON j.id = a.job_id
           JOIN companies co ON co.id = j.company_id
           LEFT JOIN offers o ON o.application_id = a.id
           WHERE a.status = 'SELECTED' OR o.id IS NOT NULL
           ORDER BY a.updated_at DESC, a.id DESC"""
    ).fetchall()
    return [dict(row) for row in rows]
