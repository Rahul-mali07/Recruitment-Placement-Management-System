"""Interview feedback, offers, joining and placement workflow."""

from __future__ import annotations

from db import get_db, log_activity
from services import ServiceError

OFFER_TRANSITIONS = {
    "OFFERED": {"ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"},
    "ACCEPTED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
    "WITHDRAWN": set(),
}


def get_feedback(interview_id: int):
    row = get_db().execute(
        "SELECT * FROM interview_feedback WHERE interview_id = ?", (interview_id,)
    ).fetchone()
    return dict(row) if row else None


def save_feedback(interview_id: int, data: dict) -> None:
    db = get_db()
    interview = db.execute(
        "SELECT i.*, a.status AS application_status, a.application_code "
        "FROM interviews i JOIN applications a ON a.id = i.application_id WHERE i.id = ?",
        (interview_id,),
    ).fetchone()
    if not interview:
        raise ServiceError("Interview not found.")
    if interview["status"] == "CANCELLED":
        raise ServiceError("Feedback cannot be added to a cancelled interview.")
    if interview["application_status"] in {"REJECTED", "WITHDRAWN"}:
        raise ServiceError("Feedback cannot change a rejected or withdrawn application.")

    db.execute(
        """INSERT INTO interview_feedback (interview_id, technical_rating,
               communication_rating, problem_solving_rating, overall_rating, remarks,
               interview_result)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(interview_id) DO UPDATE SET
               technical_rating = excluded.technical_rating,
               communication_rating = excluded.communication_rating,
               problem_solving_rating = excluded.problem_solving_rating,
               overall_rating = excluded.overall_rating,
               remarks = excluded.remarks,
               interview_result = excluded.interview_result,
               updated_at = datetime('now')""",
        (
            interview_id, data.get("technical_rating"), data.get("communication_rating"),
            data.get("problem_solving_rating"), data.get("overall_rating"),
            data.get("remarks") or None, data["interview_result"],
        ),
    )
    db.execute(
        "UPDATE interviews SET status = 'COMPLETED', updated_at = datetime('now') WHERE id = ?",
        (interview_id,),
    )
    if data["interview_result"] == "SELECTED":
        new_status = "SELECTED"
    elif data["interview_result"] == "REJECTED":
        new_status = "REJECTED"
    elif data["interview_result"] == "NEXT_ROUND":
        new_status = "INTERVIEW_SCHEDULED"
    else:
        new_status = interview["application_status"]
    db.execute(
        "UPDATE applications SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, interview["application_id"]),
    )
    log_activity("Interview feedback saved", "interview", interview_id,
                 f"{interview['interview_code']}: {data['interview_result']}")
    db.commit()


def get_offer(offer_id: int):
    row = get_db().execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
    return dict(row) if row else None


def get_offer_by_application(application_id: int):
    row = get_db().execute(
        "SELECT * FROM offers WHERE application_id = ?", (application_id,)
    ).fetchone()
    return dict(row) if row else None


def create_offer(application_id: int, data: dict) -> int:
    db = get_db()
    application = db.execute(
        "SELECT a.*, c.full_name FROM applications a JOIN candidates c ON c.id = a.candidate_id "
        "WHERE a.id = ?",
        (application_id,),
    ).fetchone()
    if not application:
        raise ServiceError("Application not found.")
    if application["status"] != "SELECTED":
        raise ServiceError("An offer can only be created for a selected candidate.")
    if get_offer_by_application(application_id):
        raise ServiceError("An offer already exists for this application.")
    cursor = db.execute(
        """INSERT INTO offers (application_id, designation, offered_package, offer_date,
               expected_joining_date, offer_status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            application_id, data["designation"], data["offered_package"],
            data["offer_date"], data.get("expected_joining_date") or None,
            data["offer_status"],
        ),
    )
    db.execute(
        "UPDATE candidates SET updated_at = datetime('now') WHERE id = ?",
        (application["candidate_id"],),
    )
    log_activity("Offer created", "offer", cursor.lastrowid,
                 f"{application['application_code']}: {data['designation']} at {data['offered_package']:g} LPA")
    db.commit()
    return cursor.lastrowid


def update_offer_status(application_id: int, new_status: str) -> None:
    offer = get_offer_by_application(application_id)
    if not offer:
        raise ServiceError("No offer exists for this application.")
    if new_status == offer["offer_status"]:
        return
    allowed = OFFER_TRANSITIONS.get(offer["offer_status"], set())
    if new_status not in allowed:
        raise ServiceError(
            f"Offer status cannot change from {offer['offer_status']} to {new_status}."
        )
    db = get_db()
    db.execute(
        "UPDATE offers SET offer_status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, offer["id"]),
    )
    log_activity("Offer status updated", "offer", offer["id"],
                 f"{offer['offer_status']} to {new_status}")
    db.commit()


def confirm_joining(application_id: int, data: dict) -> None:
    offer = get_offer_by_application(application_id)
    if not offer:
        raise ServiceError("Create and accept an offer before recording joining details.")
    if offer["offer_status"] != "ACCEPTED":
        raise ServiceError("Joining can only be confirmed for an accepted offer.")
    db = get_db()
    actual_date = data.get("actual_joining_date") or None
    db.execute(
        """UPDATE offers SET joining_status = ?, actual_joining_date = ?,
               updated_at = datetime('now') WHERE id = ?""",
        (data["joining_status"], actual_date, offer["id"]),
    )
    log_activity("Joining status updated", "offer", offer["id"],
                 f"{data['joining_status']} on {actual_date or 'not recorded'}")
    db.commit()


def mark_placed(application_id: int) -> bool:
    db = get_db()
    application = db.execute(
        """SELECT a.*, c.profile_status, c.full_name
           FROM applications a JOIN candidates c ON c.id = a.candidate_id
           WHERE a.id = ?""",
        (application_id,),
    ).fetchone()
    if not application:
        raise ServiceError("Application not found.")
    if application["status"] == "REJECTED":
        raise ServiceError("A rejected candidate cannot be marked as placed.")
    if application["status"] != "SELECTED":
        raise ServiceError("Only a selected application can be marked as placed.")
    offer = get_offer_by_application(application_id)
    if not offer:
        raise ServiceError("An offer is required before marking a candidate as placed.")
    if offer["offer_status"] != "ACCEPTED":
        raise ServiceError("The offer must be accepted before the candidate is marked as placed.")
    if offer["joining_status"] != "JOINED" or not offer["actual_joining_date"]:
        raise ServiceError("Confirm that the candidate has joined before marking them as placed.")
    if application["profile_status"] == "PLACED":
        return False
    db.execute(
        "UPDATE candidates SET profile_status = 'PLACED', updated_at = datetime('now') WHERE id = ?",
        (application["candidate_id"],),
    )
    db.execute(
        "UPDATE applications SET status = 'SELECTED', updated_at = datetime('now') WHERE id = ?",
        (application_id,),
    )
    log_activity("Candidate marked placed", "application", application_id,
                 application["full_name"])
    db.commit()
    return True
