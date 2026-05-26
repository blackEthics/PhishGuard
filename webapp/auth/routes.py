"""auth/routes.py — Google OAuth2 login/logout and user-profile pages."""
from __future__ import annotations

import logging
import os

from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from auth.oauth_client import oauth
from auth.models import User
import database.users as users_db

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _credentials_configured() -> bool:
    """Return True when Google OAuth credentials are present in config."""
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


# ── Login / OAuth flow ────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    next_url = request.args.get("next", "")
    return render_template(
        "auth/login.html",
        next_url=next_url,
        creds_ok=_credentials_configured(),
    )


@auth_bp.route("/google")
def google_login():
    # Block the redirect immediately with a friendly message when no credentials
    if not _credentials_configured():
        flash(
            "Google OAuth is not configured. "
            "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file.",
            "danger",
        )
        return redirect(url_for("auth.login"))

    next_url = request.args.get("next", url_for("index"))
    session["oauth_next"] = next_url

    # Allow overriding redirect URI via env (useful in prod / behind a proxy)
    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI",
        url_for("auth.google_callback", _external=True),
    )
    try:
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as exc:
        logger.error("Failed to initiate Google OAuth redirect: %s", exc)
        flash("Could not connect to Google. Please try again.", "danger")
        return redirect(url_for("auth.login"))


@auth_bp.route("/callback")
def google_callback():
    if not _credentials_configured():
        flash("OAuth is not configured.", "danger")
        return redirect(url_for("auth.login"))

    try:
        token = oauth.google.authorize_access_token()
    except Exception as exc:
        logger.warning("OAuth token exchange failed: %s", exc)
        flash("Google sign-in was cancelled or failed. Please try again.", "warning")
        return redirect(url_for("auth.login"))

    userinfo = token.get("userinfo")
    if not userinfo:
        flash("Google did not return account information.", "danger")
        return redirect(url_for("auth.login"))

    google_id: str = userinfo.get("sub", "")
    email: str = userinfo.get("email", "")
    name: str = userinfo.get("name") or email
    picture: str = userinfo.get("picture", "")

    if not google_id or not email:
        flash("Incomplete account data from Google.", "danger")
        return redirect(url_for("auth.login"))

    if not userinfo.get("email_verified", False):
        flash("Your Google email address is not verified.", "warning")
        return redirect(url_for("auth.login"))

    try:
        user = User.create_or_update(google_id, email, name, picture)
    except Exception as exc:
        logger.error("Failed to create/update user %s: %s", email, exc)
        flash("Account error. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)

    next_url: str = session.pop("oauth_next", url_for("index"))
    if not next_url.startswith("/"):
        next_url = url_for("index")

    logger.info("User signed in: %s", email)
    flash(f"Welcome, {name.split()[0]}!", "success")
    return redirect(next_url)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    email = current_user.email
    logout_user()
    session.clear()
    logger.info("User signed out: %s", email)
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


# ── User pages ────────────────────────────────────────────────────────────────

@auth_bp.route("/profile")
@login_required
def profile():
    scan_count = users_db.get_user_scan_count(current_user.id)
    recent = users_db.get_user_scans(current_user.id, limit=5)
    return render_template("profile.html", scan_count=scan_count, recent=recent)


@auth_bp.route("/history")
@login_required
def history():
    scans = users_db.get_user_scans(current_user.id, limit=100)
    return render_template("history.html", scans=scans)


@auth_bp.route("/settings", methods=["GET"])
@login_required
def settings():
    return render_template("settings.html")


@auth_bp.route("/settings", methods=["POST"])
@login_required
def settings_update():
    flash("Settings saved.", "success")
    return redirect(url_for("auth.settings"))


@auth_bp.route("/delete", methods=["POST"])
@login_required
def delete_account():
    user_id = current_user.id
    email = current_user.email
    logout_user()
    session.clear()
    users_db.delete_user(user_id)
    logger.info("Account deleted: %s", email)
    flash("Your account has been deleted.", "info")
    return redirect(url_for("index"))
