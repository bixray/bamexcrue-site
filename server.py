import hmac
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from waitress import serve


BASE_DIR = Path(__file__).resolve().parent
HTML_FILE = BASE_DIR / "bamexcrue.html"
DEFAULT_DATABASE = BASE_DIR / "bamexcrue.db"
MAX_REQUEST_SIZE = 16 * 1024
ALLOWED_CATEGORIES = {"contact", "deals", "goods", "health"}
STATUSES = {
    "new": "New",
    "in_progress": "In progress",
    "completed": "Completed",
}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
    DATABASE=os.environ.get("BAMEX_DATABASE", str(DEFAULT_DATABASE)),
    MAX_CONTENT_LENGTH=MAX_REQUEST_SIZE,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=os.environ.get("APP_ENV", "").lower() == "production",
)


def database_connection():
    connection = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inquiries (
                    id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    category TEXT NOT NULL CHECK (category IN ('contact', 'deals', 'goods', 'health')),
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS inquiries_created_at ON inquiries (created_at)"
            )


def email_configuration():
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return None

    sender = os.environ.get("SMTP_FROM", "").strip()
    recipient = os.environ.get("NOTIFY_TO", "kizyben47@gmail.com").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    if not sender or not EMAIL_PATTERN.fullmatch(sender):
        raise ValueError("Set SMTP_FROM to a valid email address when SMTP_HOST is configured.")
    if not recipient or not EMAIL_PATTERN.fullmatch(recipient):
        raise ValueError("Set NOTIFY_TO to a valid email address when SMTP_HOST is configured.")
    if username and not password:
        raise ValueError("Set SMTP_PASSWORD when SMTP_USERNAME is configured.")

    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "sender": sender,
        "recipient": recipient,
        "username": username,
        "password": password,
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").strip().lower()
        not in {"0", "false", "no"},
    }


app.config["EMAIL_CONFIGURATION"] = email_configuration()


def send_notification(inquiry, ticket_id, configuration):
    if configuration is None:
        return "not_configured"

    message = EmailMessage()
    message["Subject"] = "New Bamex Crue request: " + ticket_id
    message["From"] = configuration["sender"]
    message["To"] = configuration["recipient"]
    message.set_content(
        "A new website request was received.\n\n"
        "Reference: {ticket_id}\n"
        "Category: {category}\n"
        "Name: {name}\n"
        "Email: {email}\n"
        "Phone: {phone}\n\n"
        "Message:\n{message}".format(ticket_id=ticket_id, **inquiry)
    )

    try:
        with smtplib.SMTP(
            configuration["host"], configuration["port"], timeout=10
        ) as smtp:
            if configuration["use_tls"]:
                smtp.starttls()
            if configuration["username"]:
                smtp.login(configuration["username"], configuration["password"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Could not send email notification for %s", ticket_id)
        return "failed"
    return "sent"


def read_text(payload, field, maximum, required=True):
    value = payload.get(field, "")
    if not isinstance(value, str):
        raise ValueError(field + " must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(field + " is required.")
    if len(value) > maximum:
        raise ValueError(field + " must be " + str(maximum) + " characters or fewer.")
    return value


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf():
    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(400, description="The form expired. Reload the page and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config["ADMIN_PASSWORD"]:
            abort(503, description="Admin login has not been configured.")
        if session.get("admin_authenticated") is not True:
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def provide_template_helpers():
    return {"csrf_token": csrf_token, "statuses": STATUSES}


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store"
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.errorhandler(413)
def request_too_large(_error):
    if request.path.startswith("/api/"):
        return jsonify(error="The request is too large."), 413
    return "The request is too large.", 413


@app.get("/")
def home():
    return send_file(HTML_FILE)


@app.get("/api/health")
def health():
    try:
        with closing(database_connection()) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        current_app.logger.exception("Health check could not access the database")
        return jsonify(status="error"), 503
    return jsonify(status="ok")


@app.post("/api/inquiries")
def create_inquiry():
    if not request.is_json:
        return jsonify(error="Send the request as JSON."), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="The request body must be a JSON object."), 400

    try:
        inquiry = {
            "name": read_text(payload, "name", 100),
            "email": read_text(payload, "email", 254),
            "phone": read_text(payload, "phone", 40, required=False),
            "category": read_text(payload, "category", 20),
            "message": read_text(payload, "message", 4000),
        }
        if not EMAIL_PATTERN.fullmatch(inquiry["email"]):
            raise ValueError("Enter a valid email address.")
        if inquiry["category"] not in ALLOWED_CATEGORIES:
            raise ValueError("Choose a valid request category.")
    except ValueError as error:
        return jsonify(error=str(error)), 400

    request_id = str(uuid.uuid4())
    ticket_id = "BC-" + request_id[:8].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with closing(database_connection()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO inquiries
                        (id, ticket_id, created_at, name, email, phone, category, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        ticket_id,
                        created_at,
                        inquiry["name"],
                        inquiry["email"],
                        inquiry["phone"],
                        inquiry["category"],
                        inquiry["message"],
                    ),
                )
    except sqlite3.Error:
        current_app.logger.exception("Could not save request %s", ticket_id)
        return jsonify(error="We could not save your request. Please try again."), 500

    notification = send_notification(
        inquiry, ticket_id, current_app.config["EMAIL_CONFIGURATION"]
    )
    if notification == "sent":
        confirmation = "Your request has been received."
    elif notification == "failed":
        confirmation = (
            "Your request was saved, but the email alert could not be sent. "
            "Please contact us if you need confirmation."
        )
    else:
        confirmation = (
            "Your request was saved. Email notifications are not configured yet."
        )
    return (
        jsonify(
            ticketId=ticket_id,
            status="new",
            message=confirmation,
            notification=notification,
        ),
        201,
    )


@app.get("/admin/login")
def admin_login():
    if not current_app.config["ADMIN_PASSWORD"]:
        abort(503, description="Admin login has not been configured.")
    return render_template("admin_login.html")


@app.post("/admin/login")
def admin_login_submit():
    if not current_app.config["ADMIN_PASSWORD"]:
        abort(503, description="Admin login has not been configured.")
    validate_csrf()
    supplied = request.form.get("password", "")
    expected = current_app.config["ADMIN_PASSWORD"]
    if hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        session.clear()
        session.permanent = True
        session["admin_authenticated"] = True
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("admin_dashboard"))
    flash("Incorrect password. Please try again.", "error")
    return render_template("admin_login.html"), 401


@app.get("/admin")
@admin_required
def admin_dashboard():
    try:
        with closing(database_connection()) as connection:
            inquiries = connection.execute(
                """
                SELECT ticket_id, created_at, name, email, phone, category, message, status
                FROM inquiries
                ORDER BY created_at DESC
                LIMIT 500
                """
            ).fetchall()
    except sqlite3.Error:
        current_app.logger.exception("Could not load inquiry dashboard")
        abort(500, description="The inquiry list could not be loaded.")
    return render_template("admin_dashboard.html", inquiries=inquiries)


@app.post("/admin/inquiries/<ticket_id>/status")
@admin_required
def update_inquiry_status(ticket_id):
    validate_csrf()
    status = request.form.get("status", "")
    if status not in STATUSES:
        abort(400, description="Choose a valid inquiry status.")
    try:
        with closing(database_connection()) as connection:
            with connection:
                result = connection.execute(
                    "UPDATE inquiries SET status = ? WHERE ticket_id = ?",
                    (status, ticket_id),
                )
                if result.rowcount == 0:
                    abort(404)
    except sqlite3.Error:
        current_app.logger.exception("Could not update inquiry %s", ticket_id)
        abort(500, description="The inquiry status could not be updated.")
    flash("Inquiry status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/inquiries/<ticket_id>/delete")
@admin_required
def delete_inquiry(ticket_id):
    validate_csrf()
    try:
        with closing(database_connection()) as connection:
            with connection:
                result = connection.execute(
                    "DELETE FROM inquiries WHERE ticket_id = ?", (ticket_id,)
                )
                if result.rowcount == 0:
                    abort(404)
    except sqlite3.Error:
        current_app.logger.exception("Could not delete inquiry %s", ticket_id)
        abort(500, description="The inquiry could not be deleted.")
    flash("Inquiry deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/logout")
@admin_required
def admin_logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/privacy")
def privacy():
    return render_template("privacy.html")


@app.get("/terms")
def terms():
    return render_template("terms.html")


def validate_runtime_configuration():
    if len(app.config["SECRET_KEY"]) < 32:
        raise ValueError("SECRET_KEY must be at least 32 characters long.")
    if (
        os.environ.get("APP_ENV", "").lower() == "production"
        and not os.environ.get("SECRET_KEY")
    ):
        raise ValueError("Set SECRET_KEY in production to keep admin sessions secure.")
    if len(app.config["ADMIN_PASSWORD"]) < 16:
        raise ValueError("Set ADMIN_PASSWORD to a strong password of at least 16 characters.")
    app.config["EMAIL_CONFIGURATION"] = email_configuration()


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        validate_runtime_configuration()
        initialize_database()
        port = int(os.environ.get("PORT", "8000"))
    except (OSError, sqlite3.Error, ValueError) as error:
        raise SystemExit("Backend setup failed: " + str(error))

    host = os.environ.get("HOST", "127.0.0.1")
    logging.info("Bamex Crue backend listening on %s:%s", host, port)
    serve(
        app,
        host=host,
        port=port,
        threads=8,
        max_request_body_size=MAX_REQUEST_SIZE,
    )


if __name__ == "__main__":
    main()
