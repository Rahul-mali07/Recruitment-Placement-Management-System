PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN', 'RECRUITER', 'PLACEMENT_OFFICER')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candidates (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_code     TEXT NOT NULL UNIQUE,
    full_name          TEXT NOT NULL,
    email              TEXT NOT NULL UNIQUE COLLATE NOCASE,
    mobile             TEXT NOT NULL,
    date_of_birth      TEXT,
    gender             TEXT,
    qualification      TEXT NOT NULL,
    college            TEXT NOT NULL,
    university         TEXT,
    passing_year       INTEGER NOT NULL CHECK (passing_year BETWEEN 1980 AND 2100),
    score              REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    score_type         TEXT NOT NULL DEFAULT 'PERCENTAGE' CHECK (score_type IN ('PERCENTAGE', 'CGPA')),
    backlog_count      INTEGER NOT NULL DEFAULT 0 CHECK (backlog_count >= 0),
    primary_technology TEXT NOT NULL,
    secondary_skills   TEXT,
    skill_level        TEXT NOT NULL DEFAULT 'Intermediate'
                       CHECK (skill_level IN ('Basic', 'Intermediate', 'Advanced')),
    current_location   TEXT,
    preferred_location TEXT,
    profile_status     TEXT NOT NULL DEFAULT 'ACTIVE'
                       CHECK (profile_status IN ('ACTIVE', 'INACTIVE', 'ON_HOLD', 'PLACED')),
    created_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_code TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    industry     TEXT NOT NULL,
    website      TEXT,
    location     TEXT NOT NULL,
    hr_name      TEXT NOT NULL,
    hr_email     TEXT NOT NULL,
    hr_mobile    TEXT,
    company_type TEXT NOT NULL CHECK (company_type IN ('MNC', 'Startup', 'Mid-size', 'Consultancy')),
    status       TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_code            TEXT NOT NULL UNIQUE,
    company_id          INTEGER NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    title               TEXT NOT NULL,
    openings            INTEGER NOT NULL CHECK (openings > 0),
    employment_type     TEXT NOT NULL
                        CHECK (employment_type IN ('Full-time', 'Internship', 'Contract')),
    location            TEXT NOT NULL,
    min_package         REAL CHECK (min_package IS NULL OR min_package >= 0),
    max_package         REAL CHECK (max_package IS NULL OR max_package >= 0),
    qualifications      TEXT NOT NULL,
    min_percentage      REAL NOT NULL CHECK (min_percentage >= 0 AND min_percentage <= 100),
    min_passing_year    INTEGER,
    max_passing_year    INTEGER,
    max_backlogs        INTEGER NOT NULL DEFAULT 0 CHECK (max_backlogs >= 0),
    experience_required TEXT,
    technology          TEXT NOT NULL,
    required_skills     TEXT NOT NULL,
    posted_date         TEXT NOT NULL,
    deadline            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'OPEN', 'CLOSED')),
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (min_package IS NULL OR max_package IS NULL OR min_package <= max_package),
    CHECK (min_passing_year IS NULL OR max_passing_year IS NULL OR min_passing_year <= max_passing_year),
    CHECK (deadline >= posted_date)
);

CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    application_code   TEXT NOT NULL UNIQUE,
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    job_id             INTEGER NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
    recruiter_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    applied_date       TEXT NOT NULL DEFAULT (date('now')),
    eligibility_status TEXT NOT NULL DEFAULT 'NOT_CHECKED'
                       CHECK (eligibility_status IN ('NOT_CHECKED', 'ELIGIBLE', 'NOT_ELIGIBLE')),
    eligibility_reason TEXT,
    status             TEXT NOT NULL DEFAULT 'APPLIED'
                       CHECK (status IN ('APPLIED', 'ELIGIBLE', 'SHORTLISTED', 'INTERVIEW_SCHEDULED',
                                         'SELECTED', 'REJECTED', 'WITHDRAWN')),
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (candidate_id, job_id)
);

CREATE TABLE IF NOT EXISTS interviews (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_code   TEXT NOT NULL UNIQUE,
    application_id   INTEGER NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    candidate_id     INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    job_id           INTEGER NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
    company_id       INTEGER NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    round            TEXT NOT NULL CHECK (round IN ('Aptitude', 'Technical', 'Managerial', 'HR')),
    interview_date   TEXT NOT NULL,
    interview_time   TEXT NOT NULL,
    mode             TEXT NOT NULL CHECK (mode IN ('Online', 'Offline', 'Telephonic')),
    interviewer_name TEXT,
    status           TEXT NOT NULL DEFAULT 'SCHEDULED'
                     CHECK (status IN ('SCHEDULED', 'COMPLETED', 'RESCHEDULED', 'NO_SHOW', 'CANCELLED')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interview_feedback (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id           INTEGER NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    technical_rating       INTEGER CHECK (technical_rating BETWEEN 1 AND 5),
    communication_rating   INTEGER CHECK (communication_rating BETWEEN 1 AND 5),
    problem_solving_rating INTEGER CHECK (problem_solving_rating BETWEEN 1 AND 5),
    overall_rating         INTEGER CHECK (overall_rating BETWEEN 1 AND 5),
    remarks                TEXT,
    interview_result       TEXT NOT NULL
                           CHECK (interview_result IN ('NEXT_ROUND', 'SELECTED', 'REJECTED', 'ON_HOLD')),
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS offers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id        INTEGER NOT NULL UNIQUE REFERENCES applications(id) ON DELETE RESTRICT,
    designation           TEXT NOT NULL,
    offered_package       REAL NOT NULL CHECK (offered_package >= 0),
    offer_date            TEXT NOT NULL,
    expected_joining_date TEXT,
    offer_status          TEXT NOT NULL DEFAULT 'OFFERED'
                          CHECK (offer_status IN ('OFFERED', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'WITHDRAWN')),
    actual_joining_date   TEXT,
    joining_status        TEXT NOT NULL DEFAULT 'NOT_JOINED'
                          CHECK (joining_status IN ('JOINED', 'NOT_JOINED', 'DEFERRED', 'NO_SHOW')),
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   INTEGER,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(full_name);
CREATE INDEX IF NOT EXISTS idx_candidates_technology ON candidates(primary_technology);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(profile_status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_technology ON jobs(technology);
CREATE INDEX IF NOT EXISTS idx_applications_candidate ON applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_date);
CREATE INDEX IF NOT EXISTS idx_interviews_application ON interviews(application_id);
CREATE INDEX IF NOT EXISTS idx_interviews_date ON interviews(interview_date);
CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status);
CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(offer_status);
