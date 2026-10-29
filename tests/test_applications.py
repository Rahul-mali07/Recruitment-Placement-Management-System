"""Application creation, eligibility, shortlist and history tests."""

from __future__ import annotations

from conftest import fetchone, id_for, scalar


def test_create_application_and_eligibility_workflow(app, client, login):
    login("ADMIN")
    candidate_id = id_for(app, "candidates", "candidate_code", "CAN1010")
    job_id = id_for(app, "jobs", "job_code", "JOB-2026-006")

    created = client.post(
        "/applications/new",
        data={"candidate_id": candidate_id, "job_id": job_id},
        follow_redirects=False,
    )
    assert created.status_code == 302
    application = fetchone(
        app,
        "SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?",
        (candidate_id, job_id),
    )
    assert application is not None
    assert application["application_code"] == "APP1015"
    assert application["status"] == "APPLIED"
    assert application["eligibility_status"] == "NOT_CHECKED"

    checked = client.post(
        f"/applications/{application['id']}/check-eligibility",
        follow_redirects=True,
    )
    assert checked.status_code == 200
    assert b"Eligible:" in checked.data
    eligible = fetchone(
        app, "SELECT * FROM applications WHERE id = ?", (application["id"],)
    )
    assert eligible["eligibility_status"] == "ELIGIBLE"
    assert eligible["status"] == "ELIGIBLE"

    shortlisted = client.post(
        f"/applications/{application['id']}/shortlist", follow_redirects=False
    )
    assert shortlisted.status_code == 302
    assert fetchone(
        app, "SELECT status FROM applications WHERE id = ?", (application["id"],)
    )["status"] == "SHORTLISTED"

    rejected = client.post(
        f"/applications/{application['id']}/reject", follow_redirects=False
    )
    assert rejected.status_code == 302
    assert fetchone(
        app, "SELECT status FROM applications WHERE id = ?", (application["id"],)
    )["status"] == "REJECTED"


def test_duplicate_application_and_closed_job_are_rejected(app, client, login):
    login("ADMIN")
    before = scalar(app, "SELECT COUNT(*) FROM applications")
    candidate_id = id_for(app, "candidates", "candidate_code", "CAN1001")
    open_job_id = id_for(app, "jobs", "job_code", "JOB-2026-001")
    closed_job_id = id_for(app, "jobs", "job_code", "JOB-2026-007")

    duplicate = client.post(
        "/applications/new",
        data={"candidate_id": candidate_id, "job_id": open_job_id},
        follow_redirects=True,
    )
    assert duplicate.status_code == 200
    assert b"already applied" in duplicate.data

    closed = client.post(
        "/applications/new",
        data={"candidate_id": candidate_id, "job_id": closed_job_id},
        follow_redirects=True,
    )
    assert closed.status_code == 200
    assert b"only be created for open job" in closed.data
    assert scalar(app, "SELECT COUNT(*) FROM applications") == before


def test_shortlist_requires_eligibility_check(app, client, login):
    login("ADMIN")
    application = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1008'"
    )
    assert application["eligibility_status"] == "NOT_CHECKED"
    response = client.post(
        f"/applications/{application['id']}/shortlist", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"only eligible candidates can be shortlisted" in response.data
    unchanged = fetchone(
        app, "SELECT status FROM applications WHERE id = ?", (application["id"],)
    )
    assert unchanged["status"] == "APPLIED"


def test_application_history_and_filters(app, client, login):
    login("ADMIN")
    history = client.get("/applications/1/history")
    assert history.status_code == 200
    assert b"Application history" in history.data
    assert b"APP1001" in history.data
    assert b"INT1008" in history.data

    assert client.get("/applications/9999/history").status_code == 404

    filtered = client.get("/applications?status=SELECTED")
    assert filtered.status_code == 200
    assert b"APP1009" in filtered.data
    assert b"Ananya Iyer" in filtered.data
    assert b"APP1008" not in filtered.data
    assert b"/applications/1/history" not in filtered.data


def test_ineligible_application_check(app, client, login):
    login("ADMIN")
    candidate_id = id_for(app, "candidates", "candidate_code", "CAN1009")
    job_id = id_for(app, "jobs", "job_code", "JOB-2026-001")
    client.post(
        "/applications/new",
        data={"candidate_id": candidate_id, "job_id": job_id},
        follow_redirects=False,
    )
    application = fetchone(
        app,
        "SELECT * FROM applications WHERE candidate_id = ? AND job_id = ?",
        (candidate_id, job_id),
    )
    response = client.post(
        f"/applications/{application['id']}/check-eligibility",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Not eligible" in response.data
    checked = fetchone(
        app, "SELECT * FROM applications WHERE id = ?", (application["id"],)
    )
    assert checked["eligibility_status"] == "NOT_ELIGIBLE"
    assert checked["status"] == "APPLIED"
