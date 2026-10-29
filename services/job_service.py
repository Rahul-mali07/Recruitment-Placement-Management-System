"""Job opening queries and persistence."""

from __future__ import annotations

import sqlite3

from db import get_db, log_activity
from services import ServiceError


def _where(filters: dict) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if filters.get("job_code"):
        clauses.append("j.job_code LIKE ?")
        params.append(f"%{filters['job_code']}%")
    if filters.get("company_id"):
        clauses.append("j.company_id = ?")
        params.append(filters["company_id"])
    if filters.get("technology"):
        clauses.append("j.technology = ?")
        params.append(filters["technology"])
    if filters.get("location"):
        clauses.append("j.location LIKE ?")
        params.append(f"%{filters['location']}%")
    if filters.get("status"):
        clauses.append("j.status = ?")
        params.append(filters["status"])
    if filters.get("employment_type"):
        clauses.append("j.employment_type = ?")
        params.append(filters["employment_type"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_jobs(filters: dict) -> list[dict]:
    where, params = _where(filters)
    rows = get_db().execute(
        f"""SELECT j.*, c.name AS company_name, c.company_code, c.status AS company_status,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS application_count
            FROM jobs j JOIN companies c ON c.id = j.company_id
            {where}
            ORDER BY j.posted_date DESC, j.id DESC""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def summary(filters: dict) -> dict:
    where, params = _where(filters)
    row = get_db().execute(
        f"""SELECT COUNT(*) AS total,
                   SUM(CASE WHEN j.status = 'OPEN' THEN 1 ELSE 0 END) AS open_jobs,
                   SUM(CASE WHEN j.status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_jobs,
                   COALESCE(SUM(j.openings), 0) AS total_openings
            FROM jobs j JOIN companies c ON c.id = j.company_id {where}""",
        params,
    ).fetchone()
    return {
        "total": row["total"] or 0,
        "open_jobs": row["open_jobs"] or 0,
        "closed_jobs": row["closed_jobs"] or 0,
        "total_openings": row["total_openings"] or 0,
    }


def get_job(job_id: int):
    row = get_db().execute(
        """SELECT j.*, c.name AS company_name, c.company_code, c.status AS company_status,
                  (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS application_count
           FROM jobs j JOIN companies c ON c.id = j.company_id WHERE j.id = ?""",
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def get_by_code(job_code: str, exclude_id: int | None = None):
    if exclude_id:
        row = get_db().execute(
            "SELECT * FROM jobs WHERE job_code = ? COLLATE NOCASE AND id <> ?",
            (job_code, exclude_id),
        ).fetchone()
    else:
        row = get_db().execute(
            "SELECT * FROM jobs WHERE job_code = ? COLLATE NOCASE", (job_code,)
        ).fetchone()
    return dict(row) if row else None


def list_for_select() -> list[dict]:
    rows = get_db().execute(
        """SELECT j.id, j.job_code, j.title, j.technology, j.company_id,
                  c.name AS company_name, j.status
           FROM jobs j JOIN companies c ON c.id = j.company_id
           ORDER BY j.job_code"""
    ).fetchall()
    return [dict(row) for row in rows]


def _values(data: dict) -> tuple:
    return (
        data["company_id"], data["job_code"], data["title"], data["openings"],
        data["employment_type"], data["location"], data.get("min_package"),
        data.get("max_package"), data["qualifications"], data["min_percentage"],
        data.get("min_passing_year"), data.get("max_passing_year"), data["max_backlogs"],
        data.get("experience_required") or None, data["technology"],
        data["required_skills"], data["posted_date"], data["deadline"], data["status"],
    )


def create_job(data: dict, user_id: int | None = None) -> int:
    if get_by_code(data["job_code"]):
        raise ServiceError("Job code already exists.",
                           {"job_code": "This job code is already in use."})
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO jobs (company_id, job_code, title, openings, employment_type,
                   location, min_package, max_package, qualifications, min_percentage,
                   min_passing_year, max_passing_year, max_backlogs, experience_required,
                   technology, required_skills, posted_date, deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*_values(data), user_id),
        )
        log_activity("Job created", "job", cursor.lastrowid,
                     f"{data['job_code']} - {data['title']}", user_id)
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The job could not be saved. Check the company and job code.") from exc


def update_job(job_id: int, data: dict, user_id: int | None = None) -> None:
    job = get_job(job_id)
    if not job:
        raise ServiceError("Job opening not found.")
    if get_by_code(data["job_code"], exclude_id=job_id):
        raise ServiceError("Job code already exists.",
                           {"job_code": "This job code is already in use."})
    db = get_db()
    try:
        db.execute(
            """UPDATE jobs SET company_id = ?, job_code = ?, title = ?, openings = ?,
                   employment_type = ?, location = ?, min_package = ?, max_package = ?,
                   qualifications = ?, min_percentage = ?, min_passing_year = ?,
                   max_passing_year = ?, max_backlogs = ?, experience_required = ?,
                   technology = ?, required_skills = ?, posted_date = ?, deadline = ?,
                   status = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (*_values(data), job_id),
        )
        log_activity("Job updated", "job", job_id,
                     f"{data['job_code']} - {data['title']}", user_id)
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The job could not be updated. Check the company and job code.") from exc
