"""Candidate list, validation and CRUD tests."""

from __future__ import annotations

from conftest import fetchone, scalar


def candidate_form(**overrides):
    data = {
        "full_name": "Test Candidate",
        "email": "test.candidate@example.com",
        "mobile": "9876543210",
        "date_of_birth": "2003-01-15",
        "gender": "Female",
        "qualification": "BE",
        "college": "Test Engineering College",
        "university": "Test University",
        "passing_year": "2025",
        "score": "72.5",
        "backlog_count": "0",
        "primary_technology": "Python",
        "secondary_skills": "SQL, Flask",
        "skill_level": "Intermediate",
        "current_location": "Pune",
        "preferred_location": "Pune",
        "profile_status": "ACTIVE",
    }
    data.update(overrides)
    return data


def test_candidate_list_and_filters(client, login):
    login("ADMIN")
    response = client.get("/candidates")
    assert response.status_code == 200
    assert b"Rahul Patil" in response.data
    assert b"Sneha Kulkarni" in response.data
    assert b"CAN1001" in response.data

    filtered = client.get("/candidates?name=Rahul&technology=Java")
    assert filtered.status_code == 200
    assert b"Rahul Patil" in filtered.data
    assert b"Sneha Kulkarni" not in filtered.data

    empty = client.get("/candidates?name=NoSuchCandidate")
    assert empty.status_code == 200
    assert b"No candidates match" in empty.data


def test_candidate_create_and_details(app, client, login):
    login("ADMIN")
    response = client.post("/candidates/new", data=candidate_form(), follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/candidates/" in location

    created = fetchone(
        app, "SELECT * FROM candidates WHERE email = ?", ("test.candidate@example.com",)
    )
    assert created is not None
    assert created["candidate_code"] == "CAN1011"
    assert created["full_name"] == "Test Candidate"

    details = client.get(f"/candidates/{created['id']}")
    assert details.status_code == 200
    assert b"Test Candidate" in details.data
    assert b"test.candidate@example.com" in details.data


def test_candidate_duplicate_email_is_rejected(app, client, login):
    login("ADMIN")
    before = scalar(app, "SELECT COUNT(*) FROM candidates")
    response = client.post(
        "/candidates/new",
        data=candidate_form(email="rahul.patil@example.com"),
    )
    assert response.status_code == 200
    assert b"already registered" in response.data
    assert scalar(app, "SELECT COUNT(*) FROM candidates") == before


def test_candidate_invalid_mobile_and_required_fields(app, client, login):
    login("ADMIN")
    before = scalar(app, "SELECT COUNT(*) FROM candidates")
    response = client.post(
        "/candidates/new",
        data=candidate_form(full_name="", mobile="123", score="101", passing_year="1900"),
    )
    assert response.status_code == 200
    body = response.data
    assert b"Please enter candidate name" in body
    assert b"10 digits" in body
    assert b"at least 1980" in body or b"at most 100" in body
    assert scalar(app, "SELECT COUNT(*) FROM candidates") == before


def test_candidate_update(app, client, login):
    login("ADMIN")
    candidate = fetchone(app, "SELECT * FROM candidates WHERE candidate_code = 'CAN1001'")
    form = {
        "full_name": "Rahul P. Patil",
        "email": candidate["email"],
        "mobile": candidate["mobile"],
        "date_of_birth": candidate["date_of_birth"] or "",
        "gender": candidate["gender"] or "",
        "qualification": candidate["qualification"],
        "college": candidate["college"],
        "university": candidate["university"] or "",
        "passing_year": str(candidate["passing_year"]),
        "score": str(candidate["score"]),
        "backlog_count": str(candidate["backlog_count"]),
        "primary_technology": candidate["primary_technology"],
        "secondary_skills": candidate["secondary_skills"] or "",
        "skill_level": candidate["skill_level"],
        "current_location": candidate["current_location"] or "",
        "preferred_location": candidate["preferred_location"] or "",
        "profile_status": candidate["profile_status"],
    }
    response = client.post(
        f"/candidates/{candidate['id']}/edit", data=form, follow_redirects=False
    )
    assert response.status_code == 302
    updated = fetchone(app, "SELECT full_name FROM candidates WHERE id = ?", (candidate["id"],))
    assert updated["full_name"] == "Rahul P. Patil"


def test_candidate_pagination(client, login, app):
    login("ADMIN")
    with app.app_context():
        from db import get_db

        db = get_db()
        for index in range(1, 3):
            db.execute(
                """INSERT INTO candidates (
                    candidate_code, full_name, email, mobile, qualification, college,
                    passing_year, score, backlog_count, primary_technology, skill_level,
                    profile_status)
                   VALUES (?, ?, ?, ?, 'BE', 'Pagination College', 2025, 65, 0,
                           'Testing', 'Basic', 'ACTIVE')""",
                (
                    f"CAN90{index}",
                    f"Pagination Candidate {index}",
                    f"pagination{index}@example.com",
                    f"90000000{index:02d}",
                ),
            )
        db.commit()

    page_one = client.get("/candidates")
    assert page_one.status_code == 200
    assert b"Page 1 of 2" in page_one.data
    page_two = client.get("/candidates?page=2")
    assert page_two.status_code == 200
    assert b"Page 2 of 2" in page_two.data
