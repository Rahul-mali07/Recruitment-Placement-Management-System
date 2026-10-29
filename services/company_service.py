"""Company queries and persistence."""

from __future__ import annotations

import sqlite3

from db import get_db, log_activity
from services import ServiceError


def _next_code(db) -> str:
    row = db.execute(
        "SELECT MAX(CAST(SUBSTR(company_code, 4) AS INTEGER)) AS max_id FROM companies "
        "WHERE company_code LIKE 'COM%'"
    ).fetchone()
    number = (row["max_id"] or 100) + 1
    return f"COM{number}"


def list_companies(filters: dict) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if filters.get("q"):
        clauses.append("(c.name LIKE ? OR c.industry LIKE ? OR c.location LIKE ? OR c.hr_name LIKE ?)")
        term = f"%{filters['q']}%"
        params.extend([term, term, term, term])
    if filters.get("status"):
        clauses.append("c.status = ?")
        params.append(filters["status"])
    if filters.get("company_type"):
        clauses.append("c.company_type = ?")
        params.append(filters["company_type"])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = get_db().execute(
        f"""SELECT c.*,
                   (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.id AND j.status = 'OPEN') AS open_jobs,
                   (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.id) AS total_jobs
            FROM companies c {where}
            ORDER BY c.name""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def get_company(company_id: int):
    row = get_db().execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    return dict(row) if row else None


def list_for_select(active_only: bool = False) -> list[dict]:
    where = "WHERE status = 'ACTIVE'" if active_only else ""
    rows = get_db().execute(
        f"SELECT id, company_code, name, status FROM companies {where} ORDER BY name"
    ).fetchall()
    return [dict(row) for row in rows]


def create_company(data: dict, user_id: int | None = None) -> int:
    db = get_db()
    code = _next_code(db)
    try:
        cursor = db.execute(
            """INSERT INTO companies (company_code, name, industry, website, location,
                   hr_name, hr_email, hr_mobile, company_type, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code, data["name"], data["industry"], data.get("website") or None,
                data["location"], data["hr_name"], data["hr_email"],
                data.get("hr_mobile") or None, data["company_type"], data["status"], user_id,
            ),
        )
        log_activity("Company created", "company", cursor.lastrowid,
                     f"{code} - {data['name']}", user_id)
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The company could not be saved because a unique value is duplicated.") from exc


def update_company(company_id: int, data: dict, user_id: int | None = None) -> None:
    company = get_company(company_id)
    if not company:
        raise ServiceError("Company not found.")
    db = get_db()
    try:
        db.execute(
            """UPDATE companies SET name = ?, industry = ?, website = ?, location = ?,
                   hr_name = ?, hr_email = ?, hr_mobile = ?, company_type = ?, status = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                data["name"], data["industry"], data.get("website") or None,
                data["location"], data["hr_name"], data["hr_email"],
                data.get("hr_mobile") or None, data["company_type"], data["status"], company_id,
            ),
        )
        log_activity("Company updated", "company", company_id,
                     f"{company['company_code']} - {data['name']}", user_id)
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise ServiceError("The company could not be updated because a unique value is duplicated.") from exc


def toggle_status(company_id: int, user_id: int | None = None) -> str:
    company = get_company(company_id)
    if not company:
        raise ServiceError("Company not found.")
    new_status = "INACTIVE" if company["status"] == "ACTIVE" else "ACTIVE"
    db = get_db()
    db.execute(
        "UPDATE companies SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, company_id),
    )
    log_activity("Company status changed", "company", company_id,
                 f"{company['name']} set to {new_status}", user_id)
    db.commit()
    return new_status
