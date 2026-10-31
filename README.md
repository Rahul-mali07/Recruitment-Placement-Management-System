# Recruitment & Placement Management System

A complete, server-rendered recruitment and campus-placement application built for
Kiran Academy. It manages candidates, hiring companies, job openings, applications,
interviews, offers, joining and final placement, with role-based access and reports.

The interface uses plain HTML, a single shared CSS file, a local SVG logo and no
client-side JavaScript or third-party front-end frameworks.

## Features

- Secure login with ADMIN, RECRUITER and PLACEMENT_OFFICER roles.
- Session-based authentication, CSRF protection, parameterized SQLite queries and
  server-side validation.
- Candidate profiles with eligibility details, skills, status and placement history.
- Company and job-opening management, including automatic job codes.
- Application workflow: apply, check eligibility, shortlist, reject and withdraw.
- Interview scheduling, rescheduling, completion, cancellation and no-show handling.
- Selection workflow: feedback, offers, joining confirmation and mark-placed.
- Dashboard with funnel metrics, recent activity and upcoming interviews.
- Reports for company-wise placement, technology-wise placement, recruiter
  performance, pending interviews and open-job aging, with filters, CSV export and
  a print-friendly view.
- Application history view for every application.
- Responsive layout and print stylesheet.
- Seeded demonstration data and an automated pytest suite.

## Technology

- Python 3.10+ (tested with Python 3.13)
- Flask 3
- SQLite via Python's built-in `sqlite3` module
- Werkzeug password hashing
- pytest
- Jinja2 templates and one shared CSS stylesheet

## Project Structure

```
.
├── app.py                  # Application factory, routes, authentication, CLI
├── config.py               # Environment-based configuration
├── db.py                   # SQLite connection helpers and activity logging
├── schema.sql              # Database schema, constraints and indexes
├── seed.py                 # Idempotent demonstration data
├── requirements.txt
├── .env.example
├── services/               # Business logic and SQL queries by module
│   ├── candidate_service.py
│   ├── company_service.py
│   ├── job_service.py
│   ├── application_service.py
│   ├── interview_service.py
│   ├── placement_service.py
│   └── report_service.py
├── utils/                  # Validation and authorization helpers
│   ├── auth.py
│   └── validators.py
├── templates/              # All server-rendered pages and shared macros
├── static/
│   ├── css/style.css       # Single shared stylesheet
│   └── images/logo.svg
├── tests/                  # pytest suite
├── instance/               # Local SQLite database (created at runtime)
└── static/screenshots/     # Place optional screenshots here
```

## Setup on Windows

Open PowerShell in the project folder.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Configuration

The application runs with development defaults. To customize settings:

```powershell
Copy-Item .env.example .env
```

Generate a strong secret key with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Set the generated value as `SECRET_KEY` in `.env`. Other supported variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_ENV` | `development` or `production` | `development` |
| `SECRET_KEY` | Session signing key; required in production | ephemeral development key |
| `DATABASE_PATH` | Absolute path to the SQLite database | `instance/recruitment.db` |
| `CSRF_ENABLED` | Enable CSRF checks | `true` |
| `SESSION_COOKIE_SECURE` | Send cookies only over HTTPS | `true` in production |

### Initialize and Seed the Database

```powershell
python app.py --init-db
python app.py --seed-demo
```

`--seed-demo` is idempotent: it only inserts rows that are not already present, so
it is safe to rerun. It includes 10 candidates, 6 companies, 8 jobs, 14 applications,
8 interviews and 5 offers.

To create a real administrator instead of using demo data:

```powershell
python app.py --create-admin
```

You will be prompted for username, email, full name and password.

### Run the Application

```powershell
python app.py
```

Then open <http://127.0.0.1:5000>.

Useful development options:

```powershell
python app.py --host 0.0.0.0 --port 5000 --debug
```

Stop the server with `Ctrl+C`.

## Deploy on Vercel

The repository ships with `vercel.json` and exposes the Flask `app` from
`app.py`, so Vercel's zero-configuration Flask preset can deploy it directly.

1. Import the GitHub repository in the Vercel dashboard, or run `vercel` from
   the project folder.
2. Add these environment variables in the Vercel project settings:
   - `APP_ENV=production`
   - `SECRET_KEY` — a long random value (generate with
     `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `DATABASE_PATH=/tmp/recruitment.db` (optional; Vercel defaults to the temp
     directory automatically)
3. Deploy. On the first cold start the app creates and seeds the SQLite
   database in `/tmp`, so the demo logins below work immediately.

> Vercel's filesystem is ephemeral. Data written at runtime is kept per
> function instance and is not durable across cold starts or instances. For
> production use, point the app at a persistent database (for example Turso,
> PostgreSQL or another managed database).

## Demo Logins

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `Admin@12345` |
| Recruiter | `recruiter` | `Recruiter@12345` |
| Placement Officer | `placement` | `Placement@12345` |

These accounts exist only after `python app.py --seed-demo`.

## Role Permissions

| Module | Admin | Recruiter | Placement Officer |
| --- | --- | --- | --- |
| Dashboard | Yes | Yes | Yes |
| Candidates | Yes | Yes | Yes |
| Companies | Yes | Yes | No |
| Jobs | Yes | Yes | No |
| Applications | Yes | Yes | Yes |
| Interviews | Yes | Yes | Yes |
| Selection / Offer / Placement | Yes | No | Yes |
| Reports | Yes | No | Yes |

Unauthorized module access redirects to a friendly access-denied page.

## Main Routes

| Area | Routes |
| --- | --- |
| Authentication | `/login`, `/logout`, `/forgot-password` |
| Dashboard | `/dashboard` |
| Candidates | `/candidates`, `/candidates/new`, `/candidates/<id>`, `/candidates/<id>/edit` |
| Companies | `/companies`, `/companies/save`, `/companies/<id>/toggle-status` |
| Jobs | `/jobs`, `/jobs/new`, `/jobs/<id>/edit` |
| Applications | `/applications`, `/applications/new`, `/applications/<id>/history` |
| Interviews | `/interviews`, `/interviews/schedule`, `/interviews/reschedule` |
| Placement | `/placement-process`, `/placement/feedback`, `/placement/offer`, `/placement/joining`, `/placement/mark-placed` |
| Reports | `/reports`, `/reports/print`, `/reports/export` |

## Testing

Run the full test suite:

```powershell
python -m pytest -q
```

The suite covers authentication, role permissions, CSRF enforcement, validation,
candidate/company/job CRUD, applications, interviews, offer/joining/placement
transitions, reports, CSV export and confirms that all rendered pages work without
JavaScript.

Optional syntax check:

```powershell
python -m compileall -q .
```

## Reports and Printing

The reports page supports filters for company, technology, passing year and date
range. "Print View" opens a clean page without filters or navigation controls, and
"Export CSV" downloads the filtered application-level data.

## Screenshots

Add optional screenshots to `static/screenshots/` and reference them here:

```markdown
![Dashboard](static/screenshots/dashboard.png)
```

## Known Limitations

- The system uses server-rendered pages only; there is no JavaScript, live
  autocomplete or single-page navigation.
- Forgot-password is an informational page. Password reset is handled by an
  administrator.
- Reports are computed synchronously from SQLite and are intended for the dataset
  sizes typical of a training institute.
- The development server is not intended for public production use. For
  production, set `APP_ENV=production`, provide a strong `SECRET_KEY`, use HTTPS and
  serve the application with a production WSGI server.
