from functools import wraps
from pathlib import Path
import os
import re
import sqlite3

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


# =========================
# PROJECT CONFIGURATION
# =========================

BASE_DIR = Path(__file__).resolve().parent

# .env file load করবে
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "development-secret-key-change-before-live",
)

app.config["ADMIN_PASSWORD"] = os.getenv(
    "ADMIN_PASSWORD",
    "RHT@Admin2026",
)

# Maximum request size: 1 MB
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

DATABASE_PATH = BASE_DIR / "portfolio.db"


# =========================
# DATABASE FUNCTIONS
# =========================

def get_database_connection():
    """
    SQLite database connection তৈরি করে।
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    """
    প্রয়োজনীয় database table তৈরি করে।
    """
    connection = get_database_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


# =========================
# VALIDATION FUNCTIONS
# =========================

def is_valid_email(email):
    """
    Email format validate করে।
    """
    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(email_pattern, email) is not None


# =========================
# ADMIN AUTHENTICATION
# =========================

def admin_required(view_function):
    """
    Admin login ছাড়া protected page access বন্ধ রাখে।
    """

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash(
                "Please log in to access the admin dashboard.",
                "error",
            )
            return redirect(url_for("admin_login"))

        return view_function(*args, **kwargs)

    return wrapped_view


# =========================
# PUBLIC ROUTES
# =========================

@app.route("/")
def home():
    """
    Portfolio homepage দেখায়।
    """
    return render_template("index.html")


@app.route("/contact", methods=["POST"])
def contact():
    """
    Contact form validate করে এবং database-এ save করে।
    """

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    # Honeypot spam protection
    website = request.form.get("website", "").strip()

    if website:
        flash(
            "Your message has been sent successfully.",
            "success",
        )
        return redirect(url_for("home") + "#contact")

    if not name or not email or not subject or not message:
        flash(
            "Please fill in all contact form fields.",
            "error",
        )
        return redirect(url_for("home") + "#contact")

    if len(name) < 2 or len(name) > 100:
        flash(
            "Please enter a valid name.",
            "error",
        )
        return redirect(url_for("home") + "#contact")

    if not is_valid_email(email):
        flash(
            "Please enter a valid email address.",
            "error",
        )
        return redirect(url_for("home") + "#contact")

    if len(subject) < 3 or len(subject) > 200:
        flash(
            "Subject must contain between 3 and 200 characters.",
            "error",
        )
        return redirect(url_for("home") + "#contact")

    if len(message) < 10 or len(message) > 2000:
        flash(
            "Message must contain between 10 and 2000 characters.",
            "error",
        )
        return redirect(url_for("home") + "#contact")

    connection = None

    try:
        connection = get_database_connection()

        connection.execute(
            """
            INSERT INTO contact_messages (
                name,
                email,
                subject,
                message
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                subject,
                message,
            ),
        )

        connection.commit()

        flash(
            "Your message has been sent successfully. I will contact you soon.",
            "success",
        )

    except sqlite3.Error:
        flash(
            "Something went wrong while sending your message. Please try again.",
            "error",
        )

    finally:
        if connection is not None:
            connection.close()

    return redirect(url_for("home") + "#contact")


# =========================
# ADMIN ROUTES
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """
    Admin login page এবং login processing।
    """

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_messages"))

    if request.method == "POST":
        password = request.form.get("password", "")

        if password == app.config["ADMIN_PASSWORD"]:
            session.clear()
            session["admin_logged_in"] = True

            flash(
                "Admin login successful.",
                "success",
            )

            return redirect(url_for("admin_messages"))

        flash(
            "Incorrect admin password.",
            "error",
        )

    return render_template("admin_login.html")


@app.route("/admin/messages")
@admin_required
def admin_messages():
    """
    সব visitor message newest-first দেখায়।
    """

    connection = get_database_connection()

    messages = connection.execute(
        """
        SELECT
            id,
            name,
            email,
            subject,
            message,
            created_at
        FROM contact_messages
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "admin_messages.html",
        messages=messages,
    )


@app.route(
    "/admin/messages/delete/<int:message_id>",
    methods=["POST"],
)
@admin_required
def delete_message(message_id):
    """
    নির্দিষ্ট contact message delete করে।
    """

    connection = get_database_connection()

    message_exists = connection.execute(
        """
        SELECT id
        FROM contact_messages
        WHERE id = ?
        """,
        (message_id,),
    ).fetchone()

    if message_exists is None:
        connection.close()

        flash(
            "Message not found.",
            "error",
        )

        return redirect(url_for("admin_messages"))

    connection.execute(
        """
        DELETE FROM contact_messages
        WHERE id = ?
        """,
        (message_id,),
    )

    connection.commit()
    connection.close()

    flash(
        "Message deleted successfully.",
        "success",
    )

    return redirect(url_for("admin_messages"))


@app.route("/admin/logout")
@admin_required
def admin_logout():
    """
    Admin session শেষ করে।
    """

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success",
    )

    return redirect(url_for("admin_login"))


# =========================
# ERROR HANDLERS
# =========================

@app.errorhandler(404)
def page_not_found(error):
    """
    404 error response।
    """
    return (
        "<h1>404 - Page Not Found</h1>"
        "<p>The requested page does not exist.</p>",
        404,
    )


@app.errorhandler(413)
def request_too_large(error):
    """
    অতিরিক্ত বড় request reject করে।
    """

    flash(
        "The submitted request was too large.",
        "error",
    )

    return redirect(url_for("home") + "#contact")


@app.errorhandler(500)
def internal_server_error(error):
    """
    Unexpected server error response।
    """
    return (
        "<h1>500 - Internal Server Error</h1>"
        "<p>Something went wrong. Please try again later.</p>",
        500,
    )


# App import হওয়ার সময় database/table নিশ্চিত করবে
create_database()


# =========================
# LOCAL DEVELOPMENT SERVER
# =========================

if __name__ == "__main__":
    debug_mode = os.getenv(
        "FLASK_DEBUG",
        "false",
    ).lower() == "true"

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=debug_mode,
    )