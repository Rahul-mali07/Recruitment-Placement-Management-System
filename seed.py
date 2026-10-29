"""Idempotent demonstration dataset for Kiran Academy.

Demo credentials (documented in README, demo use only):
    admin / Admin@12345
    recruiter / Recruiter@12345
    placement / Placement@12345
"""

from __future__ import annotations

from werkzeug.security import generate_password_hash

from db import get_db
from services.application_service import evaluate_eligibility

DEMO_PASSWORD = "Admin@12345"

USERS = [
    ("admin", "admin@kiranacademy.example", "System Administrator", "ADMIN", DEMO_PASSWORD),
    ("recruiter", "recruiter@kiranacademy.example", "Neha Kulkarni", "RECRUITER", "Recruiter@12345"),
    ("placement", "placement@kiranacademy.example", "Amit Deshpande", "PLACEMENT_OFFICER", "Placement@12345"),
]

CANDIDATES = [
    ("CAN1001", "Rahul Patil", "rahul.patil@example.com", "9823001001", "2003-04-12", "Male",
     "BE", "Pune Institute of Technology", "Savitribai Phule Pune University", 2025, 68.0, 0,
     "Java", "SQL, Spring Boot", "Intermediate", "Pune", "Pune", "ACTIVE"),
    ("CAN1002", "Sneha Kulkarni", "sneha.kulkarni@example.com", "9823001002", "2003-09-05", "Female",
     "BE", "MIT World Peace University", "MIT-WPU", 2025, 78.0, 0,
     "Python", "Django, SQL, REST APIs", "Advanced", "Pune", "Pune", "ACTIVE"),
    ("CAN1003", "Arjun Deshmukh", "arjun.deshmukh@example.com", "9823001003", "2002-01-18", "Male",
     "BTech", "Vishwakarma Institute of Technology", "VIIT", 2024, 72.5, 0,
     "Testing", "Selenium, API Testing, JIRA", "Advanced", "Pune", "Pune", "PLACED"),
    ("CAN1004", "Priya Nair", "priya.nair@example.com", "9823001004", "2002-11-23", "Female",
     "MCA", "Pune University Department of Technology", "SPPU", 2025, 81.0, 0,
     "Data Analytics", "Power BI, SQL, Excel", "Advanced", "Mumbai", "Pune", "PLACED"),
    ("CAN1005", "Rohan Jadhav", "rohan.jadhav@example.com", "9823001005", "2004-03-30", "Male",
     "BE", "Government College of Engineering", "COEP", 2026, 61.0, 1,
     "Java", "HTML, CSS, JDBC", "Basic", "Nashik", "Pune", "ON_HOLD"),
    ("CAN1006", "Ananya Iyer", "ananya.iyer@example.com", "9823001006", "2002-07-14", "Female",
     "MCA", "Fergusson College", "SPPU", 2024, 76.0, 0,
     "Python", "Pandas, Flask, PostgreSQL", "Advanced", "Pune", "Bengaluru", "PLACED"),
    ("CAN1007", "Karan Mehta", "karan.mehta@example.com", "9823001007", "2003-12-08", "Male",
     "BE", "Sinhgad Institute of Technology", "SPPU", 2025, 66.0, 0,
     "Testing", "Manual Testing, Selenium, SQL", "Intermediate", "Pune", "Pune", "ACTIVE"),
    ("CAN1008", "Meera Joshi", "meera.joshi@example.com", "9823001008", "2004-06-21", "Female",
     "BSc", "Nowrosjee Wadia College", "SPPU", 2026, 74.0, 0,
     "Data Analytics", "SQL, Tableau, Python", "Intermediate", "Pune", "Pune", "ACTIVE"),
    ("CAN1009", "Vivek Sharma", "vivek.sharma@example.com", "9823001009", "2003-02-17", "Male",
     "BTech", "JSPM Rajarshi Shahu College of Engineering", "SPPU", 2025, 58.0, 2,
     "Java", "Core Java, MySQL", "Basic", "Solapur", "Mumbai", "INACTIVE"),
    ("CAN1010", "Ishita Rao", "ishita.rao@example.com", "9823001010", "2004-08-09", "Female",
     "BE", "Cummins College of Engineering", "SPPU", 2026, 79.0, 0,
     "Python", "Machine Learning, SQL, Flask", "Advanced", "Nagpur", "Pune", "ACTIVE"),
]

COMPANIES = [
    ("COM101", "Infosys", "IT Services", "https://www.infosys.example", "Pune",
     "Ritu Malhotra", "ritu.malhotra@infosys.example", "9800001010", "MNC", "ACTIVE"),
    ("COM102", "Tata Consultancy Services", "IT Services", "https://www.tcs.example", "Mumbai",
     "Sanjay Verma", "sanjay.verma@tcs.example", "9800001020", "MNC", "ACTIVE"),
    ("COM103", "Persistent Systems", "Software Product Engineering", "https://www.persistent.example", "Pune",
     "Kavita Deshpande", "kavita.deshpande@persistent.example", "9800001030", "Mid-size", "ACTIVE"),
    ("COM104", "Zoho Corporation", "Software Products", "https://www.zoho.example", "Chennai",
     "Harish Raman", "harish.raman@zoho.example", "9800001040", "Mid-size", "ACTIVE"),
    ("COM105", "Datamatics Global Services", "Data & Analytics", "https://www.datamatics.example", "Mumbai",
     "Farah Khan", "farah.khan@datamatics.example", "9800001050", "Consultancy", "ACTIVE"),
    ("COM106", "TechNova Solutions", "Software Consulting", "https://www.technova.example", "Pune",
     "Nilesh Pawar", "nilesh.pawar@technova.example", "9800001060", "Startup", "INACTIVE"),
]

JOBS = [
    ("JOB-2026-001", "COM101", "Associate Java Developer", 15, "Full-time", "Pune", 4.5, 6.0,
     "BE, BTech, MCA", 60.0, 2024, 2026, 0, "0-1 years", "Java",
     "Core Java, SQL, Spring Boot", "2026-09-15", "2026-11-30", "OPEN"),
    ("JOB-2026-002", "COM101", "Python Developer", 10, "Full-time", "Pune", 5.0, 7.0,
     "BE, BTech, MCA", 65.0, 2024, 2026, 0, "0-2 years", "Python",
     "Python, Django, SQL", "2026-09-20", "2026-12-05", "OPEN"),
    ("JOB-2026-003", "COM101", "QA Engineer", 8, "Full-time", "Pune", 3.8, 5.0,
     "BE, BTech, BSc, MCA", 60.0, 2024, 2026, 1, "0-1 years", "Testing",
     "Manual Testing, Selenium, SQL", "2026-09-25", "2026-12-10", "OPEN"),
    ("JOB-2026-004", "COM101", "Data Analyst", 6, "Full-time", "Pune", 4.8, 6.5,
     "BE, BTech, BSc, MCA, MSc", 65.0, 2024, 2026, 0, "0-2 years", "Data Analytics",
     "SQL, Excel, Power BI", "2026-10-01", "2026-12-15", "OPEN"),
    ("JOB-2026-005", "COM102", "Java Developer", 20, "Full-time", "Mumbai", 4.0, 6.2,
     "BE, BTech, MCA", 60.0, 2024, 2026, 1, "0-2 years", "Java",
     "Core Java, Spring, SQL", "2026-09-10", "2026-11-25", "OPEN"),
    ("JOB-2026-006", "COM103", "Software Engineering Intern", 5, "Internship", "Pune", 2.4, 3.0,
     "BE, BTech, MCA", 55.0, 2024, 2027, 0, "Fresher", "Python",
     "Python, Data Structures, SQL", "2026-10-05", "2026-12-20", "OPEN"),
    ("JOB-2026-007", "COM104", "Testing Trainee", 12, "Full-time", "Chennai", 3.2, 4.2,
     "BSc, BE, BTech", 55.0, 2024, 2026, 1, "Fresher", "Testing",
     "Manual Testing, Test Cases", "2026-08-01", "2026-09-30", "CLOSED"),
    ("JOB-2026-008", "COM105", "Data Analytics Associate", 8, "Contract", "Mumbai", 4.0, 5.5,
     "BE, BTech, MCA, MSc", 60.0, 2024, 2027, 0, "0-1 years", "Data Analytics",
     "SQL, Excel, Data Visualisation", "2026-10-15", "2026-12-31", "DRAFT"),
]

APPLICATIONS = [
    # code, candidate, job, applied date, status, checked
    ("APP1001", "CAN1001", "JOB-2026-001", "2026-10-02", "SHORTLISTED", True),
    ("APP1002", "CAN1001", "JOB-2026-002", "2026-10-03", "REJECTED", True),
    ("APP1003", "CAN1001", "JOB-2026-005", "2026-10-05", "SELECTED", True),
    ("APP1004", "CAN1002", "JOB-2026-001", "2026-10-04", "REJECTED", True),
    ("APP1005", "CAN1002", "JOB-2026-002", "2026-10-06", "SHORTLISTED", True),
    ("APP1006", "CAN1003", "JOB-2026-003", "2026-06-10", "SELECTED", True),
    ("APP1007", "CAN1004", "JOB-2026-004", "2026-07-12", "SELECTED", True),
    ("APP1008", "CAN1005", "JOB-2026-001", "2026-10-08", "APPLIED", False),
    ("APP1009", "CAN1006", "JOB-2026-002", "2026-05-18", "SELECTED", True),
    ("APP1010", "CAN1007", "JOB-2026-003", "2026-09-20", "SELECTED", True),
    ("APP1011", "CAN1008", "JOB-2026-004", "2026-10-10", "INTERVIEW_SCHEDULED", True),
    ("APP1012", "CAN1010", "JOB-2026-002", "2026-10-12", "APPLIED", False),
    ("APP1013", "CAN1009", "JOB-2026-005", "2026-09-01", "WITHDRAWN", True),
    ("APP1014", "CAN1002", "JOB-2026-006", "2026-10-14", "SHORTLISTED", True),
]

INTERVIEWS = [
    # code, application, round, date, time, mode, interviewer, status
    ("INT1001", "APP1006", "Technical", "2026-06-20", "10:00", "Online", "Ritu Malhotra", "COMPLETED"),
    ("INT1002", "APP1007", "Technical", "2026-07-22", "11:00", "Offline", "Sandeep Kulkarni", "COMPLETED"),
    ("INT1003", "APP1009", "Technical", "2026-05-28", "15:00", "Online", "Ritu Malhotra", "COMPLETED"),
    ("INT1004", "APP1010", "Technical", "2026-09-28", "10:30", "Online", "Meghna Bose", "COMPLETED"),
    ("INT1005", "APP1011", "Aptitude", "2026-11-05", "10:00", "Online", "Assessment Team", "SCHEDULED"),
    ("INT1006", "APP1005", "Technical", "2026-10-15", "12:00", "Telephonic", "Meghna Bose", "NO_SHOW"),
    ("INT1007", "APP1003", "Technical", "2026-10-10", "11:00", "Online", "Sanjay Verma", "COMPLETED"),
    ("INT1008", "APP1001", "Technical", "2026-11-03", "11:30", "Online", "Ritu Malhotra", "SCHEDULED"),
]

FEEDBACK = [
    ("INT1001", 4, 4, 4, 4, "Strong testing fundamentals and clear communication.", "SELECTED"),
    ("INT1002", 4, 5, 4, 4, "Good analytical approach and presentation.", "SELECTED"),
    ("INT1003", 5, 5, 4, 5, "Excellent Python and problem solving skills.", "SELECTED"),
    ("INT1004", 4, 4, 4, 4, "Solid manual and automation testing knowledge.", "SELECTED"),
    ("INT1007", 5, 4, 4, 4, "Strong Java fundamentals, recommended for offer.", "SELECTED"),
]

OFFERS = [
    # application, designation, package, offer date, expected joining, status, actual joining, joining status
    ("APP1006", "QA Engineer", 4.2, "2026-07-01", "2026-07-15", "ACCEPTED", "2026-07-15", "JOINED"),
    ("APP1007", "Data Analyst", 5.5, "2026-08-05", "2026-08-20", "ACCEPTED", "2026-08-20", "JOINED"),
    ("APP1009", "Python Developer", 4.5, "2026-06-10", "2026-06-25", "ACCEPTED", "2026-06-25", "JOINED"),
    ("APP1003", "Java Developer", 5.2, "2026-10-20", "2026-12-01", "ACCEPTED", None, "NOT_JOINED"),
    ("APP1010", "Software Test Engineer", 4.0, "2026-10-18", "2026-11-15", "OFFERED", None, "NOT_JOINED"),
]


def _id_for(db, table: str, column: str, value: str):
    row = db.execute(f"SELECT id FROM {table} WHERE {column} = ?", (value,)).fetchone()
    return row["id"] if row else None


def seed_demo() -> dict:
    db = get_db()
    counts = {"users": 0, "candidates": 0, "companies": 0, "jobs": 0,
              "applications": 0, "interviews": 0, "offers": 0}

    for username, email, full_name, role, password in USERS:
        cursor = db.execute(
            """INSERT OR IGNORE INTO users (username, email, full_name, password_hash, role)
               VALUES (?, ?, ?, ?, ?)""",
            (username, email, full_name, generate_password_hash(password), role),
        )
        counts["users"] += cursor.rowcount

    recruiter_id = _id_for(db, "users", "username", "recruiter")
    placement_id = _id_for(db, "users", "username", "placement")
    admin_id = _id_for(db, "users", "username", "admin")

    for row in CANDIDATES:
        cursor = db.execute(
            """INSERT OR IGNORE INTO candidates (
                candidate_code, full_name, email, mobile, date_of_birth, gender,
                qualification, college, university, passing_year, score, score_type,
                backlog_count, primary_technology, secondary_skills, skill_level,
                current_location, preferred_location, profile_status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PERCENTAGE', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*row, recruiter_id),
        )
        counts["candidates"] += cursor.rowcount

    for row in COMPANIES:
        cursor = db.execute(
            """INSERT OR IGNORE INTO companies (
                company_code, name, industry, website, location, hr_name, hr_email,
                hr_mobile, company_type, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (*row, admin_id),
        )
        counts["companies"] += cursor.rowcount

    for row in JOBS:
        (job_code, company_code, title, openings, employment_type, location, min_package,
         max_package, qualifications, min_percentage, min_year, max_year, max_backlogs,
         experience, technology, skills, posted, deadline, status) = row
        company_id = _id_for(db, "companies", "company_code", company_code)
        cursor = db.execute(
            """INSERT OR IGNORE INTO jobs (
                job_code, company_id, title, openings, employment_type, location,
                min_package, max_package, qualifications, min_percentage,
                min_passing_year, max_passing_year, max_backlogs, experience_required,
                technology, required_skills, posted_date, deadline, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_code, company_id, title, openings, employment_type, location, min_package,
             max_package, qualifications, min_percentage, min_year, max_year, max_backlogs,
             experience, technology, skills, posted, deadline, status, recruiter_id),
        )
        counts["jobs"] += cursor.rowcount

    for index, (app_code, cand_code, job_code, applied, status, checked) in enumerate(APPLICATIONS):
        candidate_id = _id_for(db, "candidates", "candidate_code", cand_code)
        job_id = _id_for(db, "jobs", "job_code", job_code)
        if not candidate_id or not job_id:
            continue
        candidate = dict(db.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
        job = dict(db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if checked:
            eligibility, reason = evaluate_eligibility(candidate, job)
        else:
            eligibility, reason = "NOT_CHECKED", "Eligibility not checked yet."
        assigned = recruiter_id if index % 4 != 3 else placement_id
        cursor = db.execute(
            """INSERT OR IGNORE INTO applications (
                application_code, candidate_id, job_id, recruiter_id, applied_date,
                eligibility_status, eligibility_reason, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (app_code, candidate_id, job_id, assigned, applied, eligibility, reason, status),
        )
        counts["applications"] += cursor.rowcount

    for code, app_code, round_name, interview_date, interview_time, mode, interviewer, status in INTERVIEWS:
        app_row = db.execute(
            "SELECT a.*, j.company_id FROM applications a JOIN jobs j ON j.id = a.job_id "
            "WHERE a.application_code = ?",
            (app_code,),
        ).fetchone()
        if not app_row:
            continue
        cursor = db.execute(
            """INSERT OR IGNORE INTO interviews (
                interview_code, application_id, candidate_id, job_id, company_id,
                round, interview_date, interview_time, mode, interviewer_name, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, app_row["id"], app_row["candidate_id"], app_row["job_id"],
             app_row["company_id"], round_name, interview_date, interview_time,
             mode, interviewer, status),
        )
        counts["interviews"] += cursor.rowcount

    for interview_code, tech, comm, problem, overall, remarks, result in FEEDBACK:
        interview_id = _id_for(db, "interviews", "interview_code", interview_code)
        if interview_id:
            db.execute(
                """INSERT OR IGNORE INTO interview_feedback (
                    interview_id, technical_rating, communication_rating,
                    problem_solving_rating, overall_rating, remarks, interview_result)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (interview_id, tech, comm, problem, overall, remarks, result),
            )

    for app_code, designation, package, offer_date, expected, status, actual, joining in OFFERS:
        application_id = _id_for(db, "applications", "application_code", app_code)
        if not application_id:
            continue
        cursor = db.execute(
            """INSERT OR IGNORE INTO offers (
                application_id, designation, offered_package, offer_date,
                expected_joining_date, offer_status, actual_joining_date, joining_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (application_id, designation, package, offer_date, expected, status, actual, joining),
        )
        counts["offers"] += cursor.rowcount

    if db.execute("SELECT COUNT(*) AS c FROM activity_log").fetchone()["c"] == 0:
        entries = [
            (admin_id, "Demo dataset seeded", "system", None,
             "Demonstration companies, jobs, candidates and workflows created.", "2026-10-01 09:00:00"),
            (recruiter_id, "Application shortlisted", "application",
             _id_for(db, "applications", "application_code", "APP1001"),
             "APP1001 shortlisted for Infosys Java Developer.", "2026-10-09 10:20:00"),
            (placement_id, "Offer created", "offer", None,
             "Offer created for Priya Nair - Data Analyst, 5.5 LPA.", "2026-08-05 14:10:00"),
            (placement_id, "Candidate marked placed", "application",
             _id_for(db, "applications", "application_code", "APP1007"),
             "Priya Nair joined Infosys as Data Analyst.", "2026-08-20 09:30:00"),
        ]
        for user_id, action, entity, entity_id, details, created_at in entries:
            db.execute(
                """INSERT INTO activity_log (user_id, action, entity_type, entity_id, details, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, action, entity, entity_id, details, created_at),
            )

    db.commit()
    counts["activity"] = db.execute("SELECT COUNT(*) AS c FROM activity_log").fetchone()["c"]
    return counts
