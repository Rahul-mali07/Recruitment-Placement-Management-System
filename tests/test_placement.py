"""Selection, offer, joining and placement workflow tests."""

from __future__ import annotations

from datetime import date, timedelta

from conftest import fetchone, id_for


def today() -> str:
    return date.today().isoformat()


def future_date(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_feedback_to_offer_to_joining_to_placed(app, client, login):
    login("PLACEMENT_OFFICER")
    interview = fetchone(
        app, "SELECT * FROM interviews WHERE interview_code = 'INT1005'"
    )
    application = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1011'"
    )
    candidate = fetchone(
        app, "SELECT * FROM candidates WHERE candidate_code = 'CAN1008'"
    )
    assert application["status"] == "INTERVIEW_SCHEDULED"
    assert candidate["profile_status"] == "ACTIVE"

    feedback = client.post(
        "/placement/feedback",
        data={
            "interview_id": interview["id"],
            "technical_rating": "4",
            "communication_rating": "5",
            "problem_solving_rating": "4",
            "overall_rating": "5",
            "remarks": "Strong data analysis skills.",
            "interview_result": "SELECTED",
        },
        follow_redirects=False,
    )
    assert feedback.status_code == 302
    selected = fetchone(
        app, "SELECT status FROM applications WHERE id = ?", (application["id"],)
    )
    assert selected["status"] == "SELECTED"
    assert fetchone(
        app, "SELECT status FROM interviews WHERE id = ?", (interview["id"],)
    )["status"] == "COMPLETED"

    offer_response = client.post(
        "/placement/offer",
        data={
            "application_id": application["id"],
            "designation": "Data Analyst",
            "offered_package": "5.5",
            "offer_date": today(),
            "expected_joining_date": future_date(),
            "offer_status": "OFFERED",
        },
        follow_redirects=False,
    )
    assert offer_response.status_code == 302
    offer = fetchone(
        app, "SELECT * FROM offers WHERE application_id = ?", (application["id"],)
    )
    assert offer is not None
    assert offer["offer_status"] == "OFFERED"
    assert offer["joining_status"] == "NOT_JOINED"

    accepted = client.post(
        "/placement/offer-status",
        data={"application_id": application["id"], "offer_status": "ACCEPTED"},
        follow_redirects=False,
    )
    assert accepted.status_code == 302
    assert fetchone(
        app, "SELECT offer_status FROM offers WHERE id = ?", (offer["id"],)
    )["offer_status"] == "ACCEPTED"

    joined = client.post(
        "/placement/joining",
        data={
            "application_id": application["id"],
            "joining_status": "JOINED",
            "actual_joining_date": today(),
        },
        follow_redirects=False,
    )
    assert joined.status_code == 302
    joined_offer = fetchone(app, "SELECT * FROM offers WHERE id = ?", (offer["id"],))
    assert joined_offer["joining_status"] == "JOINED"
    assert joined_offer["actual_joining_date"] == today()

    placed = client.post(
        "/placement/mark-placed",
        data={"application_id": application["id"]},
        follow_redirects=False,
    )
    assert placed.status_code == 302
    final_candidate = fetchone(
        app, "SELECT profile_status FROM candidates WHERE id = ?", (candidate["id"],)
    )
    assert final_candidate["profile_status"] == "PLACED"

    workflow = client.get(f"/placement-process?application_id={application['id']}")
    assert workflow.status_code == 200
    assert b"Marked placed" in workflow.data


def test_offer_validation_and_preconditions(app, client, login):
    login("PLACEMENT_OFFICER")
    shortlisted = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1001'"
    )
    precondition = client.post(
        "/placement/offer",
        data={
            "application_id": shortlisted["id"],
            "designation": "Java Developer",
            "offered_package": "4.5",
            "offer_date": today(),
            "expected_joining_date": future_date(),
            "offer_status": "OFFERED",
        },
        follow_redirects=True,
    )
    assert precondition.status_code == 200
    assert b"only be created for a selected candidate" in precondition.data
    assert fetchone(
        app, "SELECT id FROM offers WHERE application_id = ?", (shortlisted["id"],)
    ) is None

    selected = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1009'"
    )
    with app.app_context():
        from db import get_db

        db = get_db()
        db.execute("DELETE FROM offers WHERE application_id = ?", (selected["id"],))
        db.commit()

    invalid = client.post(
        "/placement/offer",
        data={
            "application_id": selected["id"],
            "designation": "",
            "offered_package": "",
            "offer_date": "",
            "offer_status": "OFFERED",
        },
    )
    assert invalid.status_code == 400
    assert b"Designation is required" in invalid.data
    assert b"This field is required" in invalid.data


def test_joining_and_placed_require_correct_sequence(app, client, login):
    login("PLACEMENT_OFFICER")
    offered = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1010'"
    )
    before_accept = client.post(
        "/placement/joining",
        data={
            "application_id": offered["id"],
            "joining_status": "JOINED",
            "actual_joining_date": today(),
        },
        follow_redirects=True,
    )
    assert before_accept.status_code == 200
    assert b"Joining can only be confirmed for an accepted offer" in before_accept.data

    accepted_not_joined = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1003'"
    )
    mark = client.post(
        "/placement/mark-placed",
        data={"application_id": accepted_not_joined["id"]},
        follow_redirects=True,
    )
    assert mark.status_code == 200
    assert b"Confirm that the candidate has joined" in mark.data
    candidate = fetchone(
        app, "SELECT profile_status FROM candidates WHERE id = ?",
        (accepted_not_joined["candidate_id"],),
    )
    assert candidate["profile_status"] != "PLACED"


def test_final_offer_status_cannot_change_again(app, client, login):
    login("PLACEMENT_OFFICER")
    application = fetchone(
        app, "SELECT * FROM applications WHERE application_code = 'APP1006'"
    )
    response = client.post(
        "/placement/offer-status",
        data={"application_id": application["id"], "offer_status": "REJECTED"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"cannot change from ACCEPTED to REJECTED" in response.data
    offer = fetchone(
        app, "SELECT offer_status FROM offers WHERE application_id = ?",
        (application["id"],),
    )
    assert offer["offer_status"] == "ACCEPTED"


def test_placement_page_for_interview_and_unknown_ids(app, client, login):
    login("PLACEMENT_OFFICER")
    interview_id = id_for(app, "interviews", "interview_code", "INT1008")
    response = client.get(f"/placement-process?interview_id={interview_id}")
    assert response.status_code == 200
    assert b"APP1001" in response.data
    assert client.get("/placement-process?interview_id=9999").status_code == 404
    assert client.get("/placement-process?application_id=9999").status_code == 404
