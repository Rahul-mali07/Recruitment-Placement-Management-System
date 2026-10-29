"""Interview scheduling and status tests."""

from __future__ import annotations

from datetime import date, timedelta

from conftest import fetchone, id_for, scalar


def future_date(days: int = 14) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def interview_form(candidate_id, company_id, job_id, **overrides):
    data = {
        "candidate_id": str(candidate_id),
        "company_id": str(company_id),
        "job_id": str(job_id),
        "round": "Technical",
        "interview_date": future_date(),
        "interview_time": "10:30",
        "mode": "Online",
        "interviewer_name": "Test Interviewer",
    }
    data.update(overrides)
    return data


def test_schedule_interview_for_shortlisted_application(app, client, login):
    login("ADMIN")
    application = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1001'"
    )
    company_id = id_for(app, "companies", "company_code", "COM101")
    before = scalar(app, "SELECT COUNT(*) FROM interviews")

    response = client.post(
        "/interviews/schedule",
        data=interview_form(
            application["candidate_id"], company_id, application["job_id"]
        ),
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/interviews")
    assert scalar(app, "SELECT COUNT(*) FROM interviews") == before + 1

    created = fetchone(
        app,
        "SELECT * FROM interviews WHERE application_id = ? ORDER BY id DESC LIMIT 1",
        (application["id"],),
    )
    assert created["status"] == "SCHEDULED"
    assert created["round"] == "Technical"
    updated = fetchone(
        app, "SELECT status FROM applications WHERE id = ?", (application["id"],)
    )
    assert updated["status"] == "INTERVIEW_SCHEDULED"


def test_schedule_rejects_past_date_and_invalid_application_state(app, client, login):
    login("ADMIN")
    application = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1001'"
    )
    company_id = id_for(app, "companies", "company_code", "COM101")

    past = client.post(
        "/interviews/schedule",
        data=interview_form(
            application["candidate_id"],
            company_id,
            application["job_id"],
            interview_date="2020-01-01",
        ),
    )
    assert past.status_code == 400
    assert b"cannot be in the past" in past.data

    applied = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1008'"
    )
    invalid_state = client.post(
        "/interviews/schedule",
        data=interview_form(
            applied["candidate_id"], company_id, applied["job_id"]
        ),
    )
    assert invalid_state.status_code == 400
    assert b"must be eligible or shortlisted" in invalid_state.data

    wrong_company = client.post(
        "/interviews/schedule",
        data=interview_form(
            application["candidate_id"], 2, application["job_id"]
        ),
    )
    assert wrong_company.status_code == 400
    assert b"does not match" in wrong_company.data


def test_reschedule_and_no_show(app, client, login):
    login("ADMIN")
    interview = fetchone(
        app, "SELECT * FROM interviews WHERE interview_code = 'INT1008'"
    )
    new_date = future_date(21)
    rescheduled = client.post(
        "/interviews/reschedule",
        data=interview_form(
            interview["candidate_id"],
            interview["company_id"],
            interview["job_id"],
            interview_id=interview["id"],
            round="Managerial",
            interview_date=new_date,
            interview_time="14:30",
            mode="Offline",
            interviewer_name="Reschedule Panel",
        ),
        follow_redirects=False,
    )
    assert rescheduled.status_code == 302
    changed = fetchone(app, "SELECT * FROM interviews WHERE id = ?", (interview["id"],))
    assert changed["status"] == "RESCHEDULED"
    assert changed["interview_date"] == new_date
    assert changed["round"] == "Managerial"

    no_show = client.post(
        f"/interviews/{interview['id']}/no-show", follow_redirects=False
    )
    assert no_show.status_code == 302
    assert fetchone(
        app, "SELECT status FROM interviews WHERE id = ?", (interview["id"],)
    )["status"] == "NO_SHOW"


def test_interview_list_and_today_panels(client, login):
    login("ADMIN")
    response = client.get("/interviews?status=SCHEDULED")
    assert response.status_code == 200
    assert b"INT1008" in response.data
    assert b"Today's interviews" in response.data
    assert b"Upcoming interviews" in response.data
