"""Dashboard, reports and pages-without-JavaScript tests."""

from __future__ import annotations


def test_dashboard_and_reports_render(client, login):
    login("ADMIN")
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"Recruitment funnel" in dashboard.data
    assert b"Upcoming interviews" in dashboard.data

    reports = client.get("/reports")
    assert reports.status_code == 200
    assert b"Recruitment Funnel" in reports.data
    assert b"Company-wise Placement" in reports.data
    assert b"Technology-wise Placement" in reports.data
    assert b"Recruiter Performance" in reports.data
    assert b"Pending Interviews" in reports.data
    assert b"Open Job Aging" in reports.data
    assert b"Reference figures" in reports.data
    assert b"Illustrative" in reports.data

    print_view = client.get("/reports/print")
    assert print_view.status_code == 200
    assert b"Back to Reports" in print_view.data
    assert b"Apply Filters" not in print_view.data


def test_report_filters_and_csv_export(client, login):
    login("ADMIN")
    filtered = client.get("/reports?technology=Python&passing_year=2025")
    assert filtered.status_code == 200
    assert b"Python" in filtered.data

    export = client.get("/reports/export?technology=Python")
    assert export.status_code == 200
    assert export.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in export.headers["Content-Disposition"]
    body = export.get_data(as_text=True)
    assert "Application ID" in body
    assert "APP1009" in body
    assert "APP1001" not in body


def test_invalid_report_filters_are_reported(client, login):
    login("ADMIN")
    response = client.get("/reports?date_from=not-a-date&technology=Unknown")
    assert response.status_code == 200
    assert b"Date From must be a valid date" in response.data
    assert b"valid technology filter" in response.data

    export = client.get("/reports/export?date_from=not-a-date", follow_redirects=True)
    assert export.status_code == 200
    assert b"Date From must be a valid date" in export.data


def test_all_required_pages_render_without_javascript(app, client, login):
    anonymous_login = client.get("/login")
    assert anonymous_login.status_code == 200
    assert b"<script" not in anonymous_login.data.lower()
    assert b"javascript:" not in anonymous_login.data.lower()

    login("ADMIN")
    pages = [
        "/dashboard",
        "/candidates",
        "/candidates/new",
        "/candidates/1",
        "/companies",
        "/jobs",
        "/jobs/new",
        "/applications",
        "/applications/1/history",
        "/interviews",
        "/placement-process?application_id=1",
        "/reports",
    ]
    with app.app_context():
        from db import get_db

        ids = {
            "interview": get_db().execute(
                "SELECT id FROM interviews WHERE interview_code = 'INT1008'"
            ).fetchone()["id"],
            "candidate": get_db().execute(
                "SELECT id FROM candidates WHERE candidate_code = 'CAN1001'"
            ).fetchone()["id"],
            "job": get_db().execute(
                "SELECT id FROM jobs WHERE job_code = 'JOB-2026-001'"
            ).fetchone()["id"],
        }
    pages.extend(
        [
            f"/interviews?reschedule={ids['interview']}",
            f"/candidates/{ids['candidate']}/edit",
            f"/jobs/{ids['job']}/edit",
            "/reports/print",
        ]
    )
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.get_data(as_text=True).lower()
        assert "<script" not in body, path
        assert "javascript:" not in body, path
        assert " onclick=" not in body, path
        assert " onchange=" not in body, path
