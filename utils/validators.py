"""Server-side form validation and normalisation."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
MOBILE_RE = re.compile(r"^\d{10}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

TECHNOLOGIES = ["Java", "Python", "Testing", "Data Analytics"]
QUALIFICATIONS = ["BE", "BTech", "BCA", "BSc", "MCA", "MSc", "ME", "MTech", "MBA", "BCom", "Other"]
COMPANY_TYPES = ["MNC", "Startup", "Mid-size", "Consultancy"]
EMPLOYMENT_TYPES = ["Full-time", "Internship", "Contract"]
SKILL_LEVELS = ["Basic", "Intermediate", "Advanced"]
PROFILE_STATUSES = ["ACTIVE", "INACTIVE", "ON_HOLD", "PLACED"]
JOB_STATUSES = ["DRAFT", "OPEN", "CLOSED"]
APPLICATION_STATUSES = [
    "APPLIED",
    "ELIGIBLE",
    "SHORTLISTED",
    "INTERVIEW_SCHEDULED",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
]
ELIGIBILITY_STATUSES = ["NOT_CHECKED", "ELIGIBLE", "NOT_ELIGIBLE"]
INTERVIEW_ROUNDS = ["Aptitude", "Technical", "Managerial", "HR"]
INTERVIEW_MODES = ["Online", "Offline", "Telephonic"]
INTERVIEW_STATUSES = ["SCHEDULED", "COMPLETED", "RESCHEDULED", "NO_SHOW", "CANCELLED"]
FEEDBACK_RESULTS = ["NEXT_ROUND", "SELECTED", "REJECTED", "ON_HOLD"]
OFFER_STATUSES = ["OFFERED", "ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"]
JOINING_STATUSES = ["JOINED", "NOT_JOINED", "DEFERRED", "NO_SHOW"]
GENDERS = ["Male", "Female", "Other", "Prefer not to say"]


def clean(value) -> str:
    return str(value).strip() if value is not None else ""


def clean_email(value) -> str:
    return clean(value).lower()


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value or ""))


def is_valid_mobile(value: str) -> bool:
    return bool(MOBILE_RE.match(value or ""))


def parse_int(value, field: str, errors: dict, *, required: bool = True,
              minimum: int | None = None, maximum: int | None = None):
    text = clean(value)
    if not text:
        if required:
            errors[field] = "This field is required."
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        errors[field] = "Enter a whole number."
        return None
    if minimum is not None and number < minimum:
        errors[field] = f"Value must be at least {minimum}."
    if maximum is not None and number > maximum:
        errors[field] = f"Value must be at most {maximum}."
    return number


def parse_float(value, field: str, errors: dict, *, required: bool = True,
                minimum: float | None = None, maximum: float | None = None):
    text = clean(value)
    if not text:
        if required:
            errors[field] = "This field is required."
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        errors[field] = "Enter a valid number."
        return None
    if minimum is not None and number < minimum:
        errors[field] = f"Value must be at least {minimum:g}."
    if maximum is not None and number > maximum:
        errors[field] = f"Value must be at most {maximum:g}."
    return number


def parse_date(value, field: str, errors: dict, *, required: bool = True):
    text = clean(value)
    if not text:
        if required:
            errors[field] = "This date is required."
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        errors[field] = "Enter a valid date."
        return None


def parse_time(value, field: str, errors: dict, *, required: bool = True):
    text = clean(value)
    if not text:
        if required:
            errors[field] = "This time is required."
        return None
    if not TIME_RE.match(text):
        errors[field] = "Enter a valid time (HH:MM)."
        return None
    return text


def validate_candidate(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {
        "full_name": clean(form.get("full_name")),
        "email": clean_email(form.get("email")),
        "mobile": clean(form.get("mobile")),
        "date_of_birth": clean(form.get("date_of_birth")),
        "gender": clean(form.get("gender")),
        "qualification": clean(form.get("qualification")),
        "college": clean(form.get("college")),
        "university": clean(form.get("university")),
        "passing_year": None,
        "score": None,
        "score_type": "PERCENTAGE",
        "backlog_count": None,
        "primary_technology": clean(form.get("primary_technology")),
        "secondary_skills": clean(form.get("secondary_skills")),
        "skill_level": clean(form.get("skill_level")) or "Intermediate",
        "current_location": clean(form.get("current_location")),
        "preferred_location": clean(form.get("preferred_location")),
        "profile_status": clean(form.get("profile_status")) or "ACTIVE",
    }

    if not data["full_name"]:
        errors["full_name"] = "Please enter candidate name."
    if not data["email"]:
        errors["email"] = "Please enter an email address."
    elif not is_valid_email(data["email"]):
        errors["email"] = "Enter a valid email address."
    if not data["mobile"]:
        errors["mobile"] = "Please enter a mobile number."
    elif not is_valid_mobile(data["mobile"]):
        errors["mobile"] = "Mobile number must contain 10 digits."
    if data["date_of_birth"]:
        dob = parse_date(data["date_of_birth"], "date_of_birth", errors)
        if dob and dob > date.today():
            errors["date_of_birth"] = "Date of birth cannot be in the future."
    if data["gender"] and data["gender"] not in GENDERS:
        errors["gender"] = "Select a valid gender option."
    if not data["qualification"]:
        errors["qualification"] = "Qualification is required."
    if not data["college"]:
        errors["college"] = "College name is required."

    data["passing_year"] = parse_int(
        form.get("passing_year"), "passing_year", errors,
        minimum=1980, maximum=date.today().year + 6,
    )
    data["score"] = parse_float(
        form.get("score"), "score", errors, minimum=0, maximum=100,
    )
    if data["score"] is not None and "score" not in errors:
        # The project uses percentage scores on a 0-100 scale.
        data["score_type"] = "PERCENTAGE"
    data["backlog_count"] = parse_int(
        form.get("backlog_count"), "backlog_count", errors, minimum=0,
    )

    if data["primary_technology"] not in TECHNOLOGIES:
        errors["primary_technology"] = "Select a valid primary technology."
    if data["skill_level"] not in SKILL_LEVELS:
        errors["skill_level"] = "Select a valid skill level."
    if data["profile_status"] not in PROFILE_STATUSES:
        errors["profile_status"] = "Select a valid profile status."

    return data, errors


def validate_company(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {
        "name": clean(form.get("name")),
        "industry": clean(form.get("industry")),
        "website": clean(form.get("website")),
        "location": clean(form.get("location")),
        "hr_name": clean(form.get("hr_name")),
        "hr_email": clean_email(form.get("hr_email")),
        "hr_mobile": clean(form.get("hr_mobile")),
        "company_type": clean(form.get("company_type")),
        "status": clean(form.get("status")) or "ACTIVE",
    }
    if not data["name"]:
        errors["name"] = "Company name is required."
    if not data["industry"]:
        errors["industry"] = "Industry is required."
    if data["website"]:
        parsed = urlparse(data["website"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors["website"] = "Enter a full URL starting with http:// or https://."
    if not data["location"]:
        errors["location"] = "Location is required."
    if not data["hr_name"]:
        errors["hr_name"] = "HR name is required."
    if not data["hr_email"]:
        errors["hr_email"] = "HR email is required."
    elif not is_valid_email(data["hr_email"]):
        errors["hr_email"] = "Enter a valid email address."
    if data["hr_mobile"] and not is_valid_mobile(data["hr_mobile"]):
        errors["hr_mobile"] = "Mobile number must contain 10 digits."
    if data["company_type"] not in COMPANY_TYPES:
        errors["company_type"] = "Select a valid company type."
    if data["status"] not in {"ACTIVE", "INACTIVE"}:
        errors["status"] = "Select a valid status."
    return data, errors


def validate_job(form, company=None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {
        "company_id": parse_int(form.get("company_id"), "company_id", errors),
        "job_code": clean(form.get("job_code")).upper(),
        "title": clean(form.get("title")),
        "openings": None,
        "employment_type": clean(form.get("employment_type")),
        "location": clean(form.get("location")),
        "min_package": None,
        "max_package": None,
        "qualifications": clean(form.get("qualifications")),
        "min_percentage": None,
        "min_passing_year": None,
        "max_passing_year": None,
        "max_backlogs": None,
        "experience_required": clean(form.get("experience_required")),
        "technology": clean(form.get("technology")),
        "required_skills": clean(form.get("required_skills")),
        "posted_date": None,
        "deadline": None,
        "status": clean(form.get("status")) or "DRAFT",
    }
    if not data["job_code"]:
        errors["job_code"] = "Job code is required."
    if not data["title"]:
        errors["title"] = "Job title is required."
    data["openings"] = parse_int(form.get("openings"), "openings", errors, minimum=1)
    if data["openings"] is not None and data["openings"] <= 0:
        errors["openings"] = "Number of openings must be greater than zero."
    if data["employment_type"] not in EMPLOYMENT_TYPES:
        errors["employment_type"] = "Select a valid employment type."
    if not data["location"]:
        errors["location"] = "Location is required."
    data["min_package"] = parse_float(
        form.get("min_package"), "min_package", errors, required=False, minimum=0,
    )
    data["max_package"] = parse_float(
        form.get("max_package"), "max_package", errors, required=False, minimum=0,
    )
    if (data["min_package"] is not None and data["max_package"] is not None
            and data["min_package"] > data["max_package"]):
        errors["min_package"] = "Minimum package cannot exceed maximum package."
    if not data["qualifications"]:
        errors["qualifications"] = "Eligibility qualifications are required."
    data["min_percentage"] = parse_float(
        form.get("min_percentage"), "min_percentage", errors, minimum=0, maximum=100,
    )
    data["min_passing_year"] = parse_int(
        form.get("min_passing_year"), "min_passing_year", errors,
        required=False, minimum=1980, maximum=2100,
    )
    data["max_passing_year"] = parse_int(
        form.get("max_passing_year"), "max_passing_year", errors,
        required=False, minimum=1980, maximum=2100,
    )
    if (data["min_passing_year"] is not None and data["max_passing_year"] is not None
            and data["min_passing_year"] > data["max_passing_year"]):
        errors["min_passing_year"] = "Minimum passing year cannot exceed the maximum."
    data["max_backlogs"] = parse_int(
        form.get("max_backlogs"), "max_backlogs", errors, minimum=0,
    )
    if data["technology"] not in TECHNOLOGIES:
        errors["technology"] = "Select a valid required technology."
    if not data["required_skills"]:
        errors["required_skills"] = "Required skills cannot be empty."
    posted = parse_date(form.get("posted_date"), "posted_date", errors)
    deadline = parse_date(form.get("deadline"), "deadline", errors)
    data["posted_date"] = posted.isoformat() if posted else ""
    data["deadline"] = deadline.isoformat() if deadline else ""
    if posted and deadline and deadline < posted:
        errors["deadline"] = "Application deadline cannot be before posted date."
    if data["status"] not in JOB_STATUSES:
        errors["status"] = "Select a valid job status."
    if company is None:
        errors["company_id"] = "Select a valid company."
    elif company["status"] != "ACTIVE" and data["status"] == "OPEN":
        errors["company_id"] = "An inactive company cannot be used for an open job."
    return data, errors


def validate_interview(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {
        "candidate_id": parse_int(form.get("candidate_id"), "candidate_id", errors),
        "company_id": parse_int(form.get("company_id"), "company_id", errors),
        "job_id": parse_int(form.get("job_id"), "job_id", errors),
        "round": clean(form.get("round")),
        "interview_date": None,
        "interview_time": None,
        "mode": clean(form.get("mode")),
        "interviewer_name": clean(form.get("interviewer_name")),
    }
    parsed_date = parse_date(form.get("interview_date"), "interview_date", errors)
    if parsed_date:
        data["interview_date"] = parsed_date.isoformat()
        if parsed_date < date.today():
            errors["interview_date"] = "Interview date cannot be in the past."
    data["interview_time"] = parse_time(form.get("interview_time"), "interview_time", errors)
    if data["round"] not in INTERVIEW_ROUNDS:
        errors["round"] = "Select a valid interview round."
    if data["mode"] not in INTERVIEW_MODES:
        errors["mode"] = "Select a valid interview mode."
    return data, errors


def validate_feedback(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {"interview_result": clean(form.get("interview_result")), "remarks": clean(form.get("remarks"))}
    for field, label in (
        ("technical_rating", "Technical rating"),
        ("communication_rating", "Communication rating"),
        ("problem_solving_rating", "Problem solving rating"),
        ("overall_rating", "Overall rating"),
    ):
        data[field] = parse_int(
            form.get(field), field, errors, required=False, minimum=1, maximum=5,
        )
    if data["interview_result"] not in FEEDBACK_RESULTS:
        errors["interview_result"] = "Select a valid interview result."
    return data, errors


def validate_offer(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {
        "designation": clean(form.get("designation")),
        "offered_package": None,
        "offer_date": None,
        "expected_joining_date": None,
        "offer_status": clean(form.get("offer_status")) or "OFFERED",
    }
    if not data["designation"]:
        errors["designation"] = "Designation is required to create an offer."
    data["offered_package"] = parse_float(
        form.get("offered_package"), "offered_package", errors, minimum=0.01,
    )
    offer_date = parse_date(form.get("offer_date"), "offer_date", errors)
    expected = parse_date(
        form.get("expected_joining_date"), "expected_joining_date", errors, required=False,
    )
    data["offer_date"] = offer_date.isoformat() if offer_date else ""
    data["expected_joining_date"] = expected.isoformat() if expected else ""
    if offer_date and expected and expected < offer_date:
        errors["expected_joining_date"] = "Expected joining date cannot be before the offer date."
    if data["offer_status"] not in OFFER_STATUSES:
        errors["offer_status"] = "Select a valid offer status."
    return data, errors


def validate_joining(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    data = {"joining_status": clean(form.get("joining_status")), "actual_joining_date": None}
    actual = parse_date(form.get("actual_joining_date"), "actual_joining_date", errors,
                        required=data["joining_status"] == "JOINED")
    if actual:
        data["actual_joining_date"] = actual.isoformat()
        if actual > date.today():
            errors["actual_joining_date"] = "Actual joining date cannot be in the future."
    if data["joining_status"] not in JOINING_STATUSES:
        errors["joining_status"] = "Select a valid joining status."
    return data, errors


def parse_date_range(args) -> tuple[str, str, list[str]]:
    errors: list[str] = []
    from_value = clean(args.get("date_from"))
    to_value = clean(args.get("date_to"))
    from_date = to_date = None
    if from_value:
        try:
            from_date = date.fromisoformat(from_value)
        except ValueError:
            errors.append("Date From must be a valid date.")
    if to_value:
        try:
            to_date = date.fromisoformat(to_value)
        except ValueError:
            errors.append("Date To must be a valid date.")
    if from_date and to_date and from_date > to_date:
        errors.append("Date From cannot be after Date To.")
    return from_value, to_value, errors
