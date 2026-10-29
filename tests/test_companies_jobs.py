"""Company and job opening tests."""

from __future__ import annotations

from conftest import fetchone, scalar


def company_form(**overrides):
    data = {
        "name": "Acme Placement Partners",
        "industry": "IT Services",
        "website": "https://acme.example",
        "location": "Pune",
        "hr_name": "Asha Rao",
        "hr_email": "asha.rao@acme.example",
        "hr_mobile": "9812345678",
        "company_type": "Startup",
        "status": "ACTIVE",
    }
    data.update(overrides)
    return data


def job_form(company_id=1, **overrides):
    data = {
        "company_id": str(company_id),
        "job_code": "JOB-2026-099",
        "title": "Junior Python Engineer",
        "openings": "5",
        "employment_type": "Full-time",
        "location": "Pune",
        "min_package": "4.0",
        "max_package": "6.0",
        "qualifications": "BE, BTech, MCA",
        "min_percentage": "60",
        "min_passing_year": "2024",
        "max_passing_year": "2026",
        "max_backlogs": "0",
        "experience_required": "0-1 years",
        "technology": "Python",
        "required_skills": "Python, SQL, Flask",
        "posted_date": "2026-10-01",
        "deadline": "2026-12-01",
        "status": "OPEN",
    }
    data.update(overrides)
    return data


def test_company_create_edit_and_toggle(app, client, login):
    login("ADMIN")
    created = client.post("/companies/save", data=company_form(), follow_redirects=False)
    assert created.status_code == 302
    company = fetchone(app, "SELECT * FROM companies WHERE name = ?", ("Acme Placement Partners",))
    assert company is not None
    assert company["company_code"] == "COM107"

    updated_form = company_form(
        name="Acme Placement Partners Pvt Ltd",
        hr_email="contact@acme.example",
        company_type="Mid-size",
    )
    updated = client.post(
        f"/companies/save",
        data={"company_id": str(company["id"]), **updated_form},
        follow_redirects=False,
    )
    assert updated.status_code == 302
    changed = fetchone(app, "SELECT * FROM companies WHERE id = ?", (company["id"],))
    assert changed["name"] == "Acme Placement Partners Pvt Ltd"
    assert changed["company_type"] == "Mid-size"

    toggled = client.post(
        f"/companies/{company['id']}/toggle-status", follow_redirects=False
    )
    assert toggled.status_code == 302
    inactive = fetchone(app, "SELECT status FROM companies WHERE id = ?", (company["id"],))
    assert inactive["status"] == "INACTIVE"


def test_company_validation(client, login, app):
    login("ADMIN")
    before = scalar(app, "SELECT COUNT(*) FROM companies")
    response = client.post(
        "/companies/save",
        data=company_form(name="", website="not-a-url", hr_email="bad-email"),
    )
    assert response.status_code == 400
    body = response.data
    assert b"Company name is required" in body
    assert b"full URL" in body
    assert b"valid email" in body
    assert scalar(app, "SELECT COUNT(*) FROM companies") == before


def test_job_create_and_list(app, client, login):
    login("ADMIN")
    response = client.post("/jobs/new", data=job_form(), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/jobs")

    job = fetchone(app, "SELECT * FROM jobs WHERE job_code = 'JOB-2026-099'")
    assert job is not None
    assert job["status"] == "OPEN"
    assert job["technology"] == "Python"

    listing = client.get("/jobs?technology=Python&status=OPEN")
    assert listing.status_code == 200
    assert b"JOB-2026-099" in listing.data
    assert b"Junior Python Engineer" in listing.data
    assert b"JOB-2026-007" not in listing.data


def test_job_create_rejects_invalid_dates_and_inactive_company(app, client, login):
    login("ADMIN")
    before = scalar(app, "SELECT COUNT(*) FROM jobs")

    invalid_dates = client.post(
        "/jobs/new",
        data=job_form(deadline="2026-09-01"),
    )
    assert invalid_dates.status_code == 200
    assert b"deadline cannot be before posted date" in invalid_dates.data

    inactive_company = client.post(
        "/jobs/new",
        data=job_form(company_id=6, job_code="JOB-2026-100"),
    )
    assert inactive_company.status_code == 200
    assert b"inactive company cannot be used" in inactive_company.data
    assert scalar(app, "SELECT COUNT(*) FROM jobs") == before


def test_job_duplicate_code_is_rejected(app, client, login):
    login("ADMIN")
    response = client.post(
        "/jobs/new",
        data=job_form(company_id=1, job_code="JOB-2026-001"),
    )
    assert response.status_code == 200
    assert b"already in use" in response.data


def test_job_update(app, client, login):
    login("ADMIN")
    job = fetchone(app, "SELECT * FROM jobs WHERE job_code = 'JOB-2026-001'")
    form = job_form(
        company_id=job["company_id"],
        job_code=job["job_code"],
        title="Associate Java Developer (Updated)",
        openings=str(job["openings"]),
        employment_type=job["employment_type"],
        location=job["location"],
        min_package=str(job["min_package"]),
        max_package=str(job["max_package"]),
        qualifications=job["qualifications"],
        min_percentage=str(job["min_percentage"]),
        min_passing_year=str(job["min_passing_year"] or ""),
        max_passing_year=str(job["max_passing_year"] or ""),
        max_backlogs=str(job["max_backlogs"]),
        experience_required=job["experience_required"] or "",
        technology=job["technology"],
        required_skills=job["required_skills"],
        posted_date=job["posted_date"],
        deadline=job["deadline"],
        status=job["status"],
    )
    response = client.post(
        f"/jobs/{job['id']}/edit", data=form, follow_redirects=False
    )
    assert response.status_code == 302
    changed = fetchone(app, "SELECT title FROM jobs WHERE id = ?", (job["id"],))
    assert changed["title"] == "Associate Java Developer (Updated)"
