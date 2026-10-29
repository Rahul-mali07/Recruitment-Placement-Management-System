"""Database-driven dashboard metrics and management reports."""

from __future__ import annotations

from datetime import date

from db import get_db

APPLICATION_JOINS = """
    FROM applications a
    JOIN candidates c ON c.id = a.candidate_id
    JOIN jobs j ON j.id = a.job_id
    JOIN companies co ON co.id = j.company_id
"""


def _where(filters: dict) -> tuple[str, list]:
    clauses = ["1 = 1"]
    params: list = []
    if filters.get("date_from"):
        clauses.append("a.applied_date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        clauses.append("a.applied_date <= ?")
        params.append(filters["date_to"])
    if filters.get("technology"):
        clauses.append("j.technology = ?")
        params.append(filters["technology"])
    if filters.get("company_id"):
        clauses.append("co.id = ?")
        params.append(filters["company_id"])
    if filters.get("recruiter_id"):
        clauses.append("a.recruiter_id = ?")
        params.append(filters["recruiter_id"])
    if filters.get("passing_year"):
        clauses.append("c.passing_year = ?")
        params.append(filters["passing_year"])
    return "WHERE " + " AND ".join(clauses), params


def dashboard_data() -> dict:
    db = get_db()
    def scalar(sql: str, params=()):
        row = db.execute(sql, params).fetchone()
        return row[0] if row else 0

    today = date.today().isoformat()
    metrics = {
        "total_candidates": scalar("SELECT COUNT(*) FROM candidates"),
        "active_candidates": scalar("SELECT COUNT(*) FROM candidates WHERE profile_status = 'ACTIVE'"),
        "companies": scalar("SELECT COUNT(*) FROM companies"),
        "open_jobs": scalar("SELECT COUNT(*) FROM jobs WHERE status = 'OPEN'"),
        "applications": scalar("SELECT COUNT(*) FROM applications"),
        "interviews": scalar("SELECT COUNT(*) FROM interviews"),
        "interviews_today": scalar(
            "SELECT COUNT(*) FROM interviews WHERE interview_date = ? "
            "AND status IN ('SCHEDULED', 'RESCHEDULED')", (today,)
        ),
        "selected": scalar("SELECT COUNT(*) FROM applications WHERE status = 'SELECTED'"),
        "placed": scalar("SELECT COUNT(*) FROM candidates WHERE profile_status = 'PLACED'"),
    }
    funnel = [
        {"label": "Applications", "count": metrics["applications"]},
        {"label": "Eligible", "count": scalar(
            "SELECT COUNT(*) FROM applications WHERE eligibility_status = 'ELIGIBLE'")},
        {"label": "Shortlisted", "count": scalar(
            "SELECT COUNT(*) FROM applications WHERE status IN "
            "('SHORTLISTED', 'INTERVIEW_SCHEDULED', 'SELECTED')")},
        {"label": "Interviewed", "count": scalar(
            "SELECT COUNT(DISTINCT application_id) FROM interviews")},
        {"label": "Selected", "count": metrics["selected"]},
        {"label": "Placed", "count": metrics["placed"]},
    ]
    top = max((item["count"] for item in funnel), default=0) or 1
    for item in funnel:
        item["percent"] = round(item["count"] * 100 / top, 1)

    upcoming = db.execute(
        """SELECT i.*, c.full_name AS candidate_name, co.name AS company_name,
                  j.title AS job_title
           FROM interviews i
           JOIN candidates c ON c.id = i.candidate_id
           JOIN companies co ON co.id = i.company_id
           JOIN jobs j ON j.id = i.job_id
           WHERE i.interview_date >= ? AND i.status IN ('SCHEDULED', 'RESCHEDULED')
           ORDER BY i.interview_date, i.interview_time LIMIT 5""",
        (today,),
    ).fetchall()
    recent_jobs = db.execute(
        """SELECT j.*, co.name AS company_name FROM jobs j
           JOIN companies co ON co.id = j.company_id
           ORDER BY j.posted_date DESC, j.id DESC LIMIT 5"""
    ).fetchall()
    recent_placements = db.execute(
        """SELECT o.*, c.full_name AS candidate_name, j.title AS job_title,
                  co.name AS company_name, a.application_code
           FROM offers o
           JOIN applications a ON a.id = o.application_id
           JOIN candidates c ON c.id = a.candidate_id
           JOIN jobs j ON j.id = a.job_id
           JOIN companies co ON co.id = j.company_id
           WHERE o.joining_status = 'JOINED'
           ORDER BY o.actual_joining_date DESC, o.id DESC LIMIT 5"""
    ).fetchall()
    activity = db.execute(
        """SELECT l.*, u.full_name AS user_name FROM activity_log l
           LEFT JOIN users u ON u.id = l.user_id
           ORDER BY l.id DESC LIMIT 8"""
    ).fetchall()
    return {
        "metrics": metrics,
        "funnel": funnel,
        "upcoming": [dict(row) for row in upcoming],
        "recent_jobs": [dict(row) for row in recent_jobs],
        "recent_placements": [dict(row) for row in recent_placements],
        "activity": [dict(row) for row in activity],
    }


def report_data(filters: dict) -> dict:
    db = get_db()
    where, params = _where(filters)

    kpi_row = db.execute(
        f"""SELECT COUNT(*) AS applications,
                   COALESCE(SUM(CASE WHEN a.status = 'SELECTED' THEN 1 ELSE 0 END), 0) AS selected,
                   COALESCE(SUM(CASE WHEN o.joining_status = 'JOINED' THEN 1 ELSE 0 END), 0) AS joined,
                   COALESCE(SUM(CASE WHEN o.offer_status = 'ACCEPTED' THEN 1 ELSE 0 END), 0) AS accepted_offers
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN offers o ON o.application_id = a.id
            {where}""",
        params,
    ).fetchone()
    applications = kpi_row["applications"] or 0
    selected = kpi_row["selected"] or 0
    joined = kpi_row["joined"] or 0
    accepted_offers = kpi_row["accepted_offers"] or 0
    interviews = db.execute(
        f"""SELECT COUNT(*) AS count FROM interviews i
            JOIN applications a ON a.id = i.application_id
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            {where}""",
        params,
    ).fetchone()["count"] or 0

    metrics = {
        "applications": applications,
        "interviews": interviews,
        "selected": selected,
        "joined": joined,
        "placement_percentage": round(joined * 100 / applications, 1) if applications else 0.0,
        "offer_to_join": round(joined * 100 / accepted_offers, 1) if accepted_offers else 0.0,
    }

    funnel_row = db.execute(
        f"""SELECT COUNT(DISTINCT a.id) AS applications,
                   COUNT(DISTINCT CASE WHEN a.eligibility_status = 'ELIGIBLE' THEN a.id END) AS eligible,
                   COUNT(DISTINCT CASE WHEN a.status IN
                       ('SHORTLISTED', 'INTERVIEW_SCHEDULED', 'SELECTED') THEN a.id END) AS shortlisted,
                   COUNT(DISTINCT i.application_id) AS interviewed,
                   COUNT(DISTINCT CASE WHEN a.status = 'SELECTED' THEN a.id END) AS selected
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN interviews i ON i.application_id = a.id
            {where}""",
        params,
    ).fetchone()
    funnel_counts = [
        ("Applications", funnel_row["applications"] or 0),
        ("Eligible", funnel_row["eligible"] or 0),
        ("Shortlisted", funnel_row["shortlisted"] or 0),
        ("Interviewed", funnel_row["interviewed"] or 0),
        ("Selected", funnel_row["selected"] or 0),
        ("Joined", joined),
    ]
    funnel_top = max((count for _, count in funnel_counts), default=0) or 1
    funnel = [
        {"label": label, "count": count, "percent": round(count * 100 / funnel_top, 1)}
        for label, count in funnel_counts
    ]

    company_rows = db.execute(
        f"""SELECT co.name,
                   COUNT(a.id) AS applications,
                   COALESCE(SUM(CASE WHEN a.status = 'SELECTED' THEN 1 ELSE 0 END), 0) AS selected,
                   COALESCE(SUM(CASE WHEN o.joining_status = 'JOINED' THEN 1 ELSE 0 END), 0) AS joined
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN offers o ON o.application_id = a.id
            {where}
            GROUP BY co.id ORDER BY joined DESC, applications DESC, co.name""",
        params,
    ).fetchall()
    company_stats = _with_percentages(company_rows)

    technology_rows = db.execute(
        f"""SELECT j.technology,
                   COUNT(a.id) AS applications,
                   COALESCE(SUM(CASE WHEN a.status = 'SELECTED' THEN 1 ELSE 0 END), 0) AS selected,
                   COALESCE(SUM(CASE WHEN o.joining_status = 'JOINED' THEN 1 ELSE 0 END), 0) AS joined
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN offers o ON o.application_id = a.id
            {where}
            GROUP BY j.technology ORDER BY joined DESC, applications DESC""",
        params,
    ).fetchall()
    technology_stats = _with_percentages(technology_rows)

    recruiter_rows = db.execute(
        f"""SELECT COALESCE(u.full_name, 'Unassigned') AS recruiter_name,
                   COUNT(a.id) AS applications,
                   COALESCE(SUM(CASE WHEN a.status IN
                       ('SHORTLISTED', 'INTERVIEW_SCHEDULED', 'SELECTED') THEN 1 ELSE 0 END), 0) AS shortlisted,
                   COALESCE(SUM(CASE WHEN a.status = 'SELECTED' THEN 1 ELSE 0 END), 0) AS selected,
                   COALESCE(SUM(CASE WHEN o.joining_status = 'JOINED' THEN 1 ELSE 0 END), 0) AS joined
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN offers o ON o.application_id = a.id
            LEFT JOIN users u ON u.id = a.recruiter_id
            {where}
            GROUP BY a.recruiter_id ORDER BY joined DESC, selected DESC, applications DESC""",
        params,
    ).fetchall()
    recruiter_stats = [dict(row) for row in recruiter_rows]

    today = date.today().isoformat()
    pending_rows = db.execute(
        f"""SELECT i.*, c.full_name AS candidate_name, co.name AS company_name,
                   j.title AS job_title
            FROM interviews i
            JOIN applications a ON a.id = i.application_id
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            {where} AND i.interview_date >= ?
                  AND i.status IN ('SCHEDULED', 'RESCHEDULED')
            ORDER BY i.interview_date, i.interview_time""",
        [*params, today],
    ).fetchall()
    pending = [dict(row) for row in pending_rows]

    aging_clauses = ["j.status = 'OPEN'"]
    aging_params: list = []
    if filters.get("technology"):
        aging_clauses.append("j.technology = ?")
        aging_params.append(filters["technology"])
    if filters.get("company_id"):
        aging_clauses.append("j.company_id = ?")
        aging_params.append(filters["company_id"])
    aging_rows = db.execute(
        f"""SELECT j.*, co.name AS company_name FROM jobs j
            JOIN companies co ON co.id = j.company_id
            WHERE {' AND '.join(aging_clauses)}
            ORDER BY j.posted_date""",
        aging_params,
    ).fetchall()
    open_jobs = []
    today_date = date.today()
    for row in aging_rows:
        item = dict(row)
        try:
            posted = date.fromisoformat(item["posted_date"])
            item["age_days"] = max(0, (today_date - posted).days)
        except (TypeError, ValueError):
            item["age_days"] = 0
        open_jobs.append(item)
    open_jobs.sort(key=lambda item: item["age_days"], reverse=True)

    return {
        "metrics": metrics,
        "funnel": funnel,
        "company_stats": company_stats,
        "technology_stats": technology_stats,
        "recruiter_stats": recruiter_stats,
        "pending": pending,
        "open_jobs": open_jobs,
    }


def _with_percentages(rows) -> list[dict]:
    result = []
    for row in rows:
        item = dict(row)
        applications = item["applications"] or 0
        item["placement_percentage"] = (
            round((item["joined"] or 0) * 100 / applications, 1) if applications else 0.0
        )
        result.append(item)
    return result


def filtered_application_rows(filters: dict) -> list[dict]:
    where, params = _where(filters)
    rows = get_db().execute(
        f"""SELECT a.application_code, c.candidate_code, c.full_name AS candidate_name,
                   c.primary_technology, c.passing_year, co.name AS company_name,
                   j.job_code, j.title AS job_title, j.technology,
                   a.applied_date, a.eligibility_status, a.status,
                   COALESCE(u.full_name, 'Unassigned') AS recruiter_name,
                   o.offer_status, o.joining_status, o.actual_joining_date
            FROM applications a
            JOIN candidates c ON c.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            JOIN companies co ON co.id = j.company_id
            LEFT JOIN offers o ON o.application_id = a.id
            LEFT JOIN users u ON u.id = a.recruiter_id
            {where}
            ORDER BY a.applied_date DESC, a.id DESC""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def recruiter_options() -> list[dict]:
    rows = get_db().execute(
        "SELECT id, full_name, role FROM users WHERE role IN ('RECRUITER', 'ADMIN') "
        "ORDER BY full_name"
    ).fetchall()
    return [dict(row) for row in rows]
