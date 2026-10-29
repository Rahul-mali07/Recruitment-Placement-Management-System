"""Kiran Academy - Recruitment & Placement Management System.

Run locally:
    python app.py

Database commands:
    python app.py --init-db
    python app.py --seed-demo
    python app.py --create-admin
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hmac
import io
import logging
import re
import secrets
import sqlite3
import sys
from datetime import date
from pathlib import Path

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db as database
from config import Config, IS_PRODUCTION
from seed import seed_demo
from services import ServiceError
from services import (application_service, candidate_service, company_service,
                      interview_service, job_service, placement_service,
                      report_service)
from utils.auth import (NAV_ITEMS, ROLE_LABELS, ROLE_PERMISSIONS, login_required,
                        module_required, safe_next_url, user_can)
from utils.validators import (APPLICATION_STATUSES, COMPANY_TYPES, ELIGIBILITY_STATUSES,
                              EMPLOYMENT_TYPES, GENDERS, INTERVIEW_MODES,
                              INTERVIEW_ROUNDS, INTERVIEW_STATUSES, JOB_STATUSES,
                              OFFER_STATUSES, PROFILE_STATUSES, QUALIFICATIONS,
                              SKILL_LEVELS, TECHNOLOGIES, clean, parse_date_range,
                              validate_candidate, validate_company, validate_feedback,
                              validate_interview, validate_job, validate_joining,
                              validate_offer)

STATUS_LABELS = {status: status.replace("_", " ").title() for status in (
    APPLICATION_STATUSES + ELIGIBILITY_STATUSES + INTERVIEW_STATUSES
    + OFFER_STATUSES + ["JOINED", "NOT_JOINED", "DEFERRED", "NO_SHOW"]
)}


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _date_display(value) -> str:
    if not value:
        return "—"
    try:
        return date.fromisoformat(str(value)).strftime("%d-%b-%Y")
    except (TypeError, ValueError):
        return str(value)


def _time_display(value) -> str:
    if not value:
        return "—"
    try:
        from datetime import time as dt_time
        return dt_time.fromisoformat(str(value)).strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return str(value)


def _status_label(value) -> str:
    if not value:
        return "—"
    return str(value).replace("_", " ").title()


def _int_arg(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_arg(args, key: str) -> str:
    return clean(args.get(key))


def _page_arg(args) -> int:
    try:
        return max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        return 1


def _return_target(default_endpoint: str) -> str:
    return safe_next_url(request.form.get("next")) or url_for(default_endpoint)


def _report_filters_from_args(args) -> tuple[dict, list[str]]:
    errors: list[str] = []
    date_from, date_to, date_errors = parse_date_range(args)
    errors.extend(date_errors)
    technology = _clean_arg(args, "technology")
    if technology and technology not in TECHNOLOGIES:
        errors.append("Select a valid technology filter.")
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "technology": technology,
        "company_id": _int_arg(args.get("company_id")),
        "recruiter_id": _int_arg(args.get("recruiter_id")),
        "passing_year": _int_arg(args.get("passing_year")),
    }
    return filters, errors


def create_app(config_object=None, test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY must be set in the environment when APP_ENV=production."
        )
    if app.config.get("IS_PRODUCTION"):
        app.config["SESSION_COOKIE_SECURE"] = True

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database.init_app(app)

    app.jinja_env.filters["date_display"] = _date_display
    app.jinja_env.filters["time_display"] = _time_display
    app.jinja_env.filters["status_label"] = _status_label
    app.jinja_env.globals["csrf_token"] = csrf_token

    def asset_version(filename: str) -> str:
        asset = Path(app.static_folder) / filename
        try:
            return str(int(asset.stat().st_mtime))
        except OSError:
            return "1"

    app.jinja_env.globals["asset_version"] = asset_version

    @app.after_request
    def prevent_development_page_caching(response: Response) -> Response:
        if not app.config.get("IS_PRODUCTION") and response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_globals():
        return {
            "nav_items": NAV_ITEMS,
            "role_labels": ROLE_LABELS,
            "can_access": user_can,
            "current_year": date.today().year,
            "today_iso": date.today().isoformat(),
            "technologies": TECHNOLOGIES,
            "qualifications": QUALIFICATIONS,
            "profile_statuses": PROFILE_STATUSES,
            "company_types": COMPANY_TYPES,
            "employment_types": EMPLOYMENT_TYPES,
            "job_statuses": JOB_STATUSES,
            "application_statuses": APPLICATION_STATUSES,
            "interview_rounds": INTERVIEW_ROUNDS,
            "interview_modes": INTERVIEW_MODES,
            "interview_statuses": INTERVIEW_STATUSES,
            "offer_statuses": OFFER_STATUSES,
            "genders": GENDERS,
            "skill_levels": SKILL_LEVELS,
        }

    @app.before_request
    def load_user_and_protect_csrf():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            row = database.get_db().execute(
                "SELECT id, username, email, full_name, role FROM users "
                "WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
            if row:
                g.user = dict(row)
                session["user_role"] = row["role"]
            else:
                session.clear()

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and app.config.get("CSRF_ENABLED", True):
            expected = session.get("_csrf_token")
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
                abort(400, description=(
                    "Your form session token is missing or expired. "
                    "Please reload the page and submit the form again."
                ))

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        errors: dict[str, str] = {}
        if request.method == "POST":
            identifier = clean(request.form.get("identifier")).lower()
            password = request.form.get("password") or ""
            selected_role = clean(request.form.get("role"))
            if not identifier:
                errors["identifier"] = "Please enter your username or email."
            if not password:
                errors["password"] = "Please enter your password."
            if selected_role not in ROLE_LABELS:
                errors["role"] = "Select a valid role."
            if not errors:
                row = database.get_db().execute(
                    "SELECT * FROM users WHERE (username = ? COLLATE NOCASE "
                    "OR email = ? COLLATE NOCASE)",
                    (identifier, identifier),
                ).fetchone()
                if not row or not check_password_hash(row["password_hash"], password):
                    errors["form"] = "Invalid username/email or password."
                elif not row["is_active"]:
                    errors["form"] = "This account is inactive. Contact the administrator."
                elif row["role"] != selected_role:
                    errors["form"] = "The selected role does not match this account."
                else:
                    session.clear()
                    session.permanent = True
                    session["user_id"] = row["id"]
                    session["user_role"] = row["role"]
                    session["user_name"] = row["full_name"] or row["username"]
                    database.log_activity("Signed in", "user", row["id"],
                                          f"{row['username']} signed in", row["id"])
                    database.get_db().commit()
                    flash(f"Welcome back, {row['full_name'] or row['username']}.", "success")
                    target = safe_next_url(request.args.get("next"))
                    return redirect(target or url_for("dashboard"))
        return render_template("login.html", errors=errors, form=request.form)

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        flash("You have been signed out.", "info")
        return redirect(url_for("login"))

    @app.get("/forgot-password")
    def forgot_password():
        return render_template("forgot-password.html")

    @app.get("/access-denied")
    @login_required
    def access_denied():
        return render_template("403.html"), 403

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @app.get("/")
    @app.get("/dashboard")
    @login_required
    @module_required("dashboard")
    def dashboard():
        data = report_service.dashboard_data()
        return render_template("dashboard.html", **data)

    # ------------------------------------------------------------------
    # Candidates
    # ------------------------------------------------------------------
    @app.get("/candidates")
    @login_required
    @module_required("candidates")
    def candidates():
        filters = {
            "candidate_id": _clean_arg(request.args, "candidate_id"),
            "name": _clean_arg(request.args, "name"),
            "mobile": _clean_arg(request.args, "mobile"),
            "email": _clean_arg(request.args, "email"),
            "technology": _clean_arg(request.args, "technology"),
            "passing_year": _clean_arg(request.args, "passing_year"),
            "qualification": _clean_arg(request.args, "qualification"),
            "status": _clean_arg(request.args, "status"),
        }
        result = candidate_service.list_candidates(filters, page=_page_arg(request.args))
        active_filters = {key: value for key, value in filters.items() if value}
        return render_template(
            "candidates.html", result=result, filters=filters,
            active_filters=active_filters,
        )

    def _candidate_form_context(mode: str, form, errors: dict, candidate=None):
        return dict(mode=mode, form=form, errors=errors, candidate=candidate)

    @app.route("/candidates/new", methods=["GET", "POST"])
    @login_required
    @module_required("candidates")
    def candidate_new():
        if request.method == "POST":
            data, errors = validate_candidate(request.form)
            if not errors:
                try:
                    candidate_id = candidate_service.create_candidate(data, g.user["id"])
                except ServiceError as exc:
                    errors.update(exc.errors)
                    flash(exc.message, "error")
                else:
                    flash(f"Candidate created successfully with ID "
                          f"{candidate_service.get_candidate(candidate_id)['candidate_code']}.", "success")
                    return redirect(url_for("candidate_details", candidate_id=candidate_id))
            return render_template(
                "candidate-form.html",
                **_candidate_form_context("create", request.form, errors),
            )
        defaults = {"skill_level": "Intermediate", "profile_status": "ACTIVE"}
        return render_template(
            "candidate-form.html",
            **_candidate_form_context("create", defaults, {}),
        )

    @app.route("/candidates/<int:candidate_id>/edit", methods=["GET", "POST"])
    @login_required
    @module_required("candidates")
    def candidate_edit(candidate_id):
        candidate = candidate_service.get_candidate(candidate_id)
        if not candidate:
            abort(404)
        if request.method == "POST":
            data, errors = validate_candidate(request.form)
            if not errors:
                try:
                    candidate_service.update_candidate(candidate_id, data, g.user["id"])
                except ServiceError as exc:
                    errors.update(exc.errors)
                    flash(exc.message, "error")
                else:
                    flash("Candidate updated successfully.", "success")
                    return redirect(url_for("candidate_details", candidate_id=candidate_id))
            return render_template(
                "candidate-form.html",
                **_candidate_form_context("edit", request.form, errors, candidate),
            )
        return render_template(
            "candidate-form.html",
            **_candidate_form_context("edit", candidate, {}, candidate),
        )

    @app.get("/candidates/<int:candidate_id>")
    @login_required
    @module_required("candidates")
    def candidate_details(candidate_id):
        profile = candidate_service.candidate_profile(candidate_id)
        if not profile:
            abort(404)
        return render_template("candidate-details.html", **profile)

    # ------------------------------------------------------------------
    # Companies
    # ------------------------------------------------------------------
    def _companies_context(form=None, errors=None, editing=None):
        filters = {
            "q": _clean_arg(request.args, "q"),
            "status": _clean_arg(request.args, "status"),
            "company_type": _clean_arg(request.args, "company_type"),
        }
        companies_list = company_service.list_companies(filters)
        if form is None:
            if editing:
                form = editing
            else:
                form = {"status": "ACTIVE", "company_type": "MNC"}
        return dict(
            companies=companies_list, filters=filters, form=form,
            errors=errors or {}, editing=editing,
        )

    @app.get("/companies")
    @login_required
    @module_required("companies")
    def companies():
        editing = None
        edit_id = _int_arg(request.args.get("edit"))
        if edit_id:
            editing = company_service.get_company(edit_id)
            if not editing:
                abort(404)
        return render_template("companies.html", **_companies_context(editing=editing))

    @app.post("/companies/save")
    @login_required
    @module_required("companies")
    def company_save():
        company_id = _int_arg(request.form.get("company_id"))
        editing = company_service.get_company(company_id) if company_id else None
        if company_id and not editing:
            abort(404)
        data, errors = validate_company(request.form)
        if errors:
            return render_template(
                "companies.html",
                **_companies_context(form=request.form, errors=errors, editing=editing),
            ), 400
        try:
            if editing:
                company_service.update_company(company_id, data, g.user["id"])
                flash(f"{data['name']} updated successfully.", "success")
            else:
                new_id = company_service.create_company(data, g.user["id"])
                created = company_service.get_company(new_id)
                flash(f"Company created successfully with ID {created['company_code']}.", "success")
        except ServiceError as exc:
            flash(exc.message, "error")
            return render_template(
                "companies.html",
                **_companies_context(form=request.form, errors=exc.errors, editing=editing),
            ), 400
        return redirect(url_for("companies"))

    @app.post("/companies/<int:company_id>/toggle-status")
    @login_required
    @module_required("companies")
    def company_toggle_status(company_id):
        try:
            new_status = company_service.toggle_status(company_id, g.user["id"])
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash(f"Company status changed to {new_status.title()}.", "success")
        return redirect(_return_target("companies"))

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------
    def _job_page_context(form=None, errors=None, job=None):
        filters = {
            "job_code": _clean_arg(request.args, "job_code"),
            "company_id": _clean_arg(request.args, "company_id"),
            "technology": _clean_arg(request.args, "technology"),
            "location": _clean_arg(request.args, "location"),
            "status": _clean_arg(request.args, "status"),
            "employment_type": _clean_arg(request.args, "employment_type"),
        }
        return dict(
            jobs=job_service.list_jobs(filters),
            summary=job_service.summary(filters),
            filters=filters,
            companies=company_service.list_for_select(active_only=False),
            form=form or {
                "posted_date": date.today().isoformat(),
                "status": "DRAFT",
                "employment_type": "Full-time",
                "max_backlogs": 0,
                "min_percentage": 60,
            },
            errors=errors or {},
            job=job,
        )

    @app.get("/jobs")
    @login_required
    @module_required("jobs")
    def jobs():
        return render_template("jobs.html", **_job_page_context())

    def _job_form_context(mode: str, form, errors: dict, job=None):
        companies_list = company_service.list_for_select(active_only=False)
        return dict(mode=mode, form=form, errors=errors, job=job, companies=companies_list)

    @app.route("/jobs/new", methods=["GET", "POST"])
    @login_required
    @module_required("jobs")
    def job_new():
        if request.method == "POST":
            company = company_service.get_company(_int_arg(request.form.get("company_id")) or 0)
            data, errors = validate_job(request.form, company)
            if not errors:
                try:
                    job_id = job_service.create_job(data, g.user["id"])
                except ServiceError as exc:
                    errors.update(exc.errors)
                    flash(exc.message, "error")
                else:
                    flash("Job opening created successfully.", "success")
                    return redirect(url_for("jobs"))
            return render_template(
                "job-form.html",
                **_job_form_context("create", request.form, errors),
            )
        defaults = {
            "posted_date": date.today().isoformat(),
            "status": "DRAFT",
            "employment_type": "Full-time",
            "max_backlogs": 0,
            "min_percentage": 60,
        }
        return render_template(
            "job-form.html", **_job_form_context("create", defaults, {}),
        )

    @app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    @login_required
    @module_required("jobs")
    def job_edit(job_id):
        job = job_service.get_job(job_id)
        if not job:
            abort(404)
        if request.method == "POST":
            company = company_service.get_company(_int_arg(request.form.get("company_id")) or 0)
            data, errors = validate_job(request.form, company)
            if not errors:
                try:
                    job_service.update_job(job_id, data, g.user["id"])
                except ServiceError as exc:
                    errors.update(exc.errors)
                    flash(exc.message, "error")
                else:
                    flash("Job opening updated successfully.", "success")
                    return redirect(url_for("jobs"))
            return render_template(
                "job-form.html",
                **_job_form_context("edit", request.form, errors, job),
            )
        return render_template(
            "job-form.html", **_job_form_context("edit", job, {}, job),
        )

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    def _application_filters() -> tuple[dict, list[str]]:
        errors: list[str] = []
        date_from, date_to, date_errors = parse_date_range(request.args)
        errors.extend(date_errors)
        return {
            "application_id": _clean_arg(request.args, "application_id"),
            "candidate": _clean_arg(request.args, "candidate"),
            "company_id": _clean_arg(request.args, "company_id"),
            "job_id": _clean_arg(request.args, "job_id"),
            "status": _clean_arg(request.args, "status"),
            "date_from": date_from,
            "date_to": date_to,
        }, errors

    def _applications_context(filters: dict):
        return dict(
            applications=application_service.list_applications(filters),
            pipeline=application_service.summary(filters),
            filters=filters,
            companies=company_service.list_for_select(active_only=False),
            jobs=job_service.list_for_select(),
            candidates= candidate_service.list_candidates_for_select(),
        )

    @app.get("/applications")
    @login_required
    @module_required("applications")
    def applications():
        filters, errors = _application_filters()
        for error in errors:
            flash(error, "error")
        return render_template("applications.html", **_applications_context(filters))

    @app.post("/applications/new")
    @login_required
    @module_required("applications")
    def application_new():
        candidate_id = _int_arg(request.form.get("candidate_id"))
        job_id = _int_arg(request.form.get("job_id"))
        if not candidate_id or not job_id:
            flash("Select both a candidate and a job opening.", "error")
            return redirect(url_for("applications"))
        recruiter_id = g.user["id"] if g.user["role"] in {"RECRUITER", "ADMIN"} else None
        try:
            application_service.create_application(candidate_id, job_id, recruiter_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Application created. Check eligibility before shortlisting.", "success")
        return redirect(_return_target("applications"))

    @app.post("/applications/<int:application_id>/check-eligibility")
    @login_required
    @module_required("applications")
    def application_check_eligibility(application_id):
        try:
            status, reason = application_service.check_eligibility(application_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash(reason, "success" if status == "ELIGIBLE" else "warning")
        return redirect(_return_target("applications"))

    @app.post("/applications/<int:application_id>/shortlist")
    @login_required
    @module_required("applications")
    def application_shortlist(application_id):
        try:
            application_service.shortlist(application_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Application shortlisted successfully.", "success")
        return redirect(_return_target("applications"))

    @app.post("/applications/<int:application_id>/reject")
    @login_required
    @module_required("applications")
    def application_reject(application_id):
        try:
            application_service.reject(application_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Application rejected.", "info")
        return redirect(_return_target("applications"))

    @app.get("/applications/<int:application_id>/history")
    @login_required
    @module_required("applications")
    def application_history(application_id):
        data = application_service.history(application_id)
        if not data:
            abort(404)
        return render_template("application-history.html", **data)

    # ------------------------------------------------------------------
    # Interviews
    # ------------------------------------------------------------------
    def _interview_context(form=None, errors=None, rescheduling=None):
        filters = {
            "q": _clean_arg(request.args, "q"),
            "status": _clean_arg(request.args, "status"),
            "date_from": _clean_arg(request.args, "date_from"),
            "date_to": _clean_arg(request.args, "date_to"),
        }
        return dict(
            interviews=interview_service.list_interviews(filters),
            today_list=interview_service.today_interviews(),
            upcoming=interview_service.upcoming_interviews(),
            filters=filters,
            candidates=candidate_service.list_candidates_for_select(),
            companies=company_service.list_for_select(active_only=False),
            jobs=job_service.list_for_select(),
            form=form or {
                "round": "Technical",
                "mode": "Online",
                "interview_date": "",
            },
            errors=errors or {},
            rescheduling=rescheduling,
        )

    @app.get("/interviews")
    @login_required
    @module_required("interviews")
    def interviews():
        rescheduling = None
        reschedule_id = _int_arg(request.args.get("reschedule"))
        if reschedule_id:
            rescheduling = interview_service.get_interview(reschedule_id)
            if not rescheduling:
                abort(404)
        prefill = None
        if rescheduling:
            prefill = dict(rescheduling)
        elif request.args.get("candidate_id") or request.args.get("job_id"):
            prefill = {
                "candidate_id": _clean_arg(request.args, "candidate_id"),
                "job_id": _clean_arg(request.args, "job_id"),
                "company_id": _clean_arg(request.args, "company_id"),
                "round": "Technical",
                "mode": "Online",
                "interview_date": "",
            }
        return render_template(
            "interviews.html",
            **_interview_context(form=prefill, rescheduling=rescheduling),
        )

    @app.post("/interviews/schedule")
    @login_required
    @module_required("interviews")
    def interview_schedule():
        data, errors = validate_interview(request.form)
        if not errors:
            try:
                interview_service.schedule(data)
            except ServiceError as exc:
                flash(exc.message, "error")
                errors["form"] = exc.message
            else:
                flash("Interview scheduled successfully.", "success")
                return redirect(url_for("interviews"))
        return render_template(
            "interviews.html",
            **_interview_context(form=request.form, errors=errors),
        ), 400

    @app.post("/interviews/reschedule")
    @login_required
    @module_required("interviews")
    def interview_reschedule():
        interview_id = _int_arg(request.form.get("interview_id"))
        interview = interview_service.get_interview(interview_id) if interview_id else None
        if not interview:
            abort(404)
        data, errors = validate_interview(request.form)
        if not errors:
            for field in ("candidate_id", "company_id", "job_id"):
                if str(data[field]) != str(interview[field]):
                    errors[field] = "The candidate, company and job cannot change when rescheduling."
                    break
        if not errors:
            try:
                interview_service.reschedule(interview_id, data)
            except ServiceError as exc:
                flash(exc.message, "error")
                errors["form"] = exc.message
            else:
                flash("Interview rescheduled successfully.", "success")
                return redirect(url_for("interviews"))
        return render_template(
            "interviews.html",
            **_interview_context(form=request.form, errors=errors, rescheduling=interview),
        ), 400

    @app.post("/interviews/<int:interview_id>/no-show")
    @login_required
    @module_required("interviews")
    def interview_no_show(interview_id):
        try:
            interview_service.mark_no_show(interview_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Interview marked as no show.", "info")
        return redirect(_return_target("interviews"))

    # ------------------------------------------------------------------
    # Selection, Offer & Placement
    # ------------------------------------------------------------------
    def _placement_context(interview=None, application=None, offer=None,
                           form=None, errors=None, offer_form=None, joining_form=None):
        applications_list = application_service.selected_for_placement()
        interviews_list = []
        feedback = None
        if application:
            interviews_list = interview_service.list_for_application(application["id"])
            offer = offer or placement_service.get_offer_by_application(application["id"])
            if interview:
                feedback = placement_service.get_feedback(interview["id"])
        return dict(
            applications=applications_list,
            application=application,
            interview=interview,
            interviews=interviews_list,
            offer=offer,
            feedback=feedback,
            form=form or {},
            errors=errors or {},
            offer_form=offer_form or {},
            joining_form=joining_form or {},
        )

    @app.get("/placement-process")
    @login_required
    @module_required("placement")
    def placement_process():
        interview = None
        application = None
        offer = None
        interview_id = _int_arg(request.args.get("interview_id"))
        application_id = _int_arg(request.args.get("application_id"))
        offer_id = _int_arg(request.args.get("offer_id"))
        if interview_id:
            interview = interview_service.get_interview(interview_id)
            if not interview:
                abort(404)
            application = application_service.get_application(interview["application_id"])
        elif application_id:
            application = application_service.get_application(application_id)
            if not application:
                abort(404)
        elif offer_id:
            offer = placement_service.get_offer(offer_id)
            if not offer:
                abort(404)
            application = application_service.get_application(offer["application_id"])
        if application and not offer:
            offer = placement_service.get_offer_by_application(application["id"])
        return render_template(
            "placement-process.html",
            **_placement_context(interview=interview, application=application, offer=offer),
        )

    @app.post("/placement/feedback")
    @login_required
    @module_required("placement")
    def placement_feedback():
        interview_id = _int_arg(request.form.get("interview_id"))
        interview = interview_service.get_interview(interview_id) if interview_id else None
        if not interview:
            abort(404)
        data, errors = validate_feedback(request.form)
        if errors:
            application = application_service.get_application(interview["application_id"])
            return render_template(
                "placement-process.html",
                **_placement_context(interview=interview, application=application,
                                     form=request.form, errors=errors),
            ), 400
        try:
            placement_service.save_feedback(interview_id, data)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Interview feedback saved and interview marked completed.", "success")
        return redirect(url_for("placement_process", interview_id=interview_id))

    @app.post("/placement/offer")
    @login_required
    @module_required("placement")
    def placement_offer():
        application_id = _int_arg(request.form.get("application_id"))
        application = application_service.get_application(application_id) if application_id else None
        if not application:
            abort(404)
        data, errors = validate_offer(request.form)
        if errors:
            return render_template(
                "placement-process.html",
                **_placement_context(application=application, offer_form=request.form,
                                     errors=errors),
            ), 400
        try:
            placement_service.create_offer(application_id, data)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Offer created successfully.", "success")
        return redirect(url_for("placement_process", application_id=application_id))

    @app.post("/placement/offer-status")
    @login_required
    @module_required("placement")
    def placement_offer_status():
        application_id = _int_arg(request.form.get("application_id"))
        new_status = clean(request.form.get("offer_status")).upper()
        if not application_id:
            abort(404)
        try:
            placement_service.update_offer_status(application_id, new_status)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash(f"Offer status updated to {new_status.replace('_', ' ').title()}.", "success")
        return redirect(url_for("placement_process", application_id=application_id))

    @app.post("/placement/joining")
    @login_required
    @module_required("placement")
    def placement_joining():
        application_id = _int_arg(request.form.get("application_id"))
        if not application_id:
            abort(404)
        data, errors = validate_joining(request.form)
        if errors:
            application = application_service.get_application(application_id)
            if not application:
                abort(404)
            return render_template(
                "placement-process.html",
                **_placement_context(application=application, joining_form=request.form,
                                     errors=errors),
            ), 400
        try:
            placement_service.confirm_joining(application_id, data)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            flash("Joining details confirmed.", "success")
        return redirect(url_for("placement_process", application_id=application_id))

    @app.post("/placement/mark-placed")
    @login_required
    @module_required("placement")
    def placement_mark_placed():
        application_id = _int_arg(request.form.get("application_id"))
        if not application_id:
            abort(404)
        try:
            changed = placement_service.mark_placed(application_id)
        except ServiceError as exc:
            flash(exc.message, "error")
        else:
            if changed:
                flash("Candidate marked as placed. The placement is recorded in reports.", "success")
            else:
                flash("This candidate is already marked as placed.", "info")
        return redirect(url_for("placement_process", application_id=application_id))

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    def _reports_context(filters: dict) -> dict:
        data = report_service.report_data(filters)
        export_filters = {
            key: value for key, value in filters.items()
            if value not in (None, "")
        }
        return dict(
            data, filters=filters, export_filters=export_filters,
            companies=company_service.list_for_select(active_only=False),
            recruiters=report_service.recruiter_options(),
        )

    @app.get("/reports")
    @login_required
    @module_required("reports")
    def reports():
        filters, errors = _report_filters_from_args(request.args)
        for error in errors:
            flash(error, "error")
        return render_template(
            "reports.html", **_reports_context(filters), print_mode=False,
        )

    @app.get("/reports/print")
    @login_required
    @module_required("reports")
    def reports_print():
        filters, errors = _report_filters_from_args(request.args)
        for error in errors:
            flash(error, "error")
        return render_template(
            "reports.html", **_reports_context(filters), print_mode=True,
        )

    @app.get("/reports/export")
    @login_required
    @module_required("reports")
    def reports_export():
        filters, errors = _report_filters_from_args(request.args)
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("reports"))
        rows = report_service.filtered_application_rows(filters)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Application ID", "Candidate ID", "Candidate", "Technology", "Passing Year",
            "Company", "Job Code", "Job Title", "Applied Date", "Eligibility",
            "Application Status", "Recruiter", "Offer Status", "Joining Status",
            "Actual Joining Date",
        ])
        for row in rows:
            writer.writerow([
                row["application_code"], row["candidate_code"], row["candidate_name"],
                row["primary_technology"], row["passing_year"], row["company_name"],
                row["job_code"], row["job_title"], row["applied_date"],
                row["eligibility_status"], row["status"], row["recruiter_name"],
                row["offer_status"] or "", row["joining_status"] or "",
                row["actual_joining_date"] or "",
            ])
        filename = f"kiran-academy-report-{date.today().isoformat()}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(error):
        return render_template("400.html", message=getattr(error, "description", None)), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unexpected server error", exc_info=error)
        return render_template("500.html"), 500

    return app


# ----------------------------------------------------------------------
# Command-line interface
# ----------------------------------------------------------------------
def _create_admin(app: Flask) -> int:
    print("Create the first administrator (input is not stored in shell history).")
    username = input("Username: ").strip()
    email = input("Email: ").strip().lower()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not username or not email or not full_name:
        print("Username, email and full name are required.", file=sys.stderr)
        return 1
    if not re.match(r"^[A-Za-z0-9_.-]{3,40}$", username):
        print("Username must be 3-40 characters using letters, numbers, dot, dash or underscore.",
              file=sys.stderr)
        return 1
    if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", email):
        print("Enter a valid email address.", file=sys.stderr)
        return 1
    if len(password) < 10:
        print("Password must be at least 10 characters.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    with app.app_context():
        database.init_db()
        connection = database.get_db()
        try:
            connection.execute(
                "INSERT INTO users (username, email, full_name, password_hash, role) "
                "VALUES (?, ?, ?, ?, 'ADMIN')",
                (username, email, full_name, generate_password_hash(password)),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            print("A user with that username or email already exists.", file=sys.stderr)
            return 1
    print(f"Administrator '{username}' created successfully.")
    return 0


def _run_seed(app: Flask) -> int:
    with app.app_context():
        database.init_db()
        counts = seed_demo()
    print("Demo data seeded (idempotent). New rows created:", counts)
    print("Demo logins: admin / Admin@12345, recruiter / Recruiter@12345, "
          "placement / Placement@12345")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiran Academy Recruitment & Placement System")
    parser.add_argument("--init-db", action="store_true", help="Create the SQLite schema.")
    parser.add_argument("--seed-demo", action="store_true", help="Insert idempotent demo data.")
    parser.add_argument("--create-admin", action="store_true", help="Interactively create an admin.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app()

    if args.init_db:
        with app.app_context():
            database.init_db()
        print(f"Database initialized at {app.config['DATABASE']}")
        return 0
    if args.seed_demo:
        return _run_seed(app)
    if args.create_admin:
        return _create_admin(app)

    if IS_PRODUCTION and not app.config.get("SECRET_KEY"):
        print("SECRET_KEY must be configured in production.", file=sys.stderr)
        return 1
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
