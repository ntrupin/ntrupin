import base64
import functools
import json
import time
from types import SimpleNamespace

import click
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from server import db, meta

bp = Blueprint("auth", __name__, url_prefix="/auth")

SESSION_ACCESS_TOKEN_KEY = "sb_access_token"
SESSION_REFRESH_TOKEN_KEY = "sb_refresh_token"
SESSION_USER_ID_KEY = "sb_user_id"
SESSION_USER_EMAIL_KEY = "sb_user_email"

def _clear_supabase_session() -> None:
    session.pop(SESSION_ACCESS_TOKEN_KEY, None)
    session.pop(SESSION_REFRESH_TOKEN_KEY, None)
    session.pop(SESSION_USER_ID_KEY, None)
    session.pop(SESSION_USER_EMAIL_KEY, None)
    session.pop("bootstrap_admin_seeded", None)

def _set_session_user(user_id: str | None, email: str | None) -> None:
    if user_id:
        session[SESSION_USER_ID_KEY] = user_id
    else:
        session.pop(SESSION_USER_ID_KEY, None)

    normalized_email = (email or "").strip().lower()
    if normalized_email:
        session[SESSION_USER_EMAIL_KEY] = normalized_email
    else:
        session.pop(SESSION_USER_EMAIL_KEY, None)

def _session_tokens() -> tuple[str | None, str | None]:
    return (
        session.get(SESSION_ACCESS_TOKEN_KEY),
        session.get(SESSION_REFRESH_TOKEN_KEY),
    )

def _decode_jwt_payload(token: str) -> dict | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None

def _token_is_expiring(access_token: str, leeway_seconds: int = 45) -> bool:
    payload = _decode_jwt_payload(access_token)
    if not payload:
        return True
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return True
    return int(exp) <= int(time.time()) + leeway_seconds

def _token_is_expired(access_token: str) -> bool:
    payload = _decode_jwt_payload(access_token)
    if not payload:
        return True
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return True
    return int(exp) <= int(time.time())

def _refresh_auth_session(refresh_token: str | None):
    if not refresh_token:
        return None

    try:
        refreshed = db.get().auth.refresh_session(refresh_token)
    except Exception:
        return None

    refreshed_session = refreshed.session
    if not refreshed_session:
        return None

    session[SESSION_ACCESS_TOKEN_KEY] = refreshed_session.access_token
    session[SESSION_REFRESH_TOKEN_KEY] = refreshed_session.refresh_token
    db.get().postgrest.auth(refreshed_session.access_token)
    user = refreshed.user or refreshed_session.user
    if user:
        _set_session_user(user.id, user.email)
    return user

def _load_user_from_session():
    access_token, refresh_token = _session_tokens()
    if not access_token:
        return None

    cached_user_id = session.get(SESSION_USER_ID_KEY)
    cached_user_email = session.get(SESSION_USER_EMAIL_KEY)

    if _token_is_expiring(access_token):
        refreshed_user = _refresh_auth_session(refresh_token)
        if refreshed_user:
            return refreshed_user
        # Avoid dropping auth on transient refresh failures while token is still valid.
        if cached_user_id and not _token_is_expired(access_token):
            return SimpleNamespace(id=cached_user_id, email=cached_user_email)
        return None

    if cached_user_id:
        return SimpleNamespace(
            id=cached_user_id,
            email=cached_user_email,
        )

    auth_client = db.get().auth

    try:
        user_response = auth_client.get_user(access_token)
        user = user_response.user if user_response else None
    except Exception:
        user = None

    if user is not None:
        _set_session_user(user.id, user.email)
        return user
    return _refresh_auth_session(refresh_token)

@bp.before_app_request
def load_logged_in_user():
    g.user = None
    auth_user = _load_user_from_session()
    if not auth_user:
        _clear_supabase_session()
        return

    user_email = (auth_user.email or "").strip().lower()
    is_bootstrap_admin = db.is_bootstrap_admin_email(user_email)
    if is_bootstrap_admin and not session.get("bootstrap_admin_seeded"):
        try:
            db.upsert_user_role(auth_user.id, "admin")
            session["bootstrap_admin_seeded"] = True
        except Exception:
            pass

    role: str | None = None
    group_ids: list[int] = []

    try:
        role = db.get_user_role(auth_user.id)
        group_ids = db.get_user_group_ids(auth_user.id)
    except Exception:
        role = None
        group_ids = []

    is_admin = role == "admin" or is_bootstrap_admin
    if is_admin and role != "admin":
        try:
            db.upsert_user_role(auth_user.id, "admin")
            role = "admin"
        except Exception:
            pass
    effective_role = "admin" if is_admin else (role or "member")

    if not group_ids:
        try:
            db.sync_default_role_group(
                user_id=auth_user.id,
                role=effective_role,
                created_by=auth_user.id,
            )
            group_ids = db.get_user_group_ids(auth_user.id)
        except Exception:
            pass

    g.user = {
        "id": auth_user.id,
        "email": user_email,
        "role": effective_role,
        "is_admin": is_admin,
        "group_ids": group_ids,
    }

@bp.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        try:
            auth_response = db.get().auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password,
                }
            )
        except Exception:
            flash("Incorrect email or password.")
            return redirect(url_for("auth.login"))

        if not auth_response.session:
            flash("Login failed.")
            return redirect(url_for("auth.login"))

        session.clear()
        session[SESSION_ACCESS_TOKEN_KEY] = auth_response.session.access_token
        session[SESSION_REFRESH_TOKEN_KEY] = auth_response.session.refresh_token
        _set_session_user(
            auth_response.user.id if auth_response.user else None,
            auth_response.user.email if auth_response.user else email,
        )
        session.permanent = True
        return redirect(url_for("index"))

    cfg = meta.Metadata()
    cfg.title = "Login"
    return render_template("auth/login.jinja", **cfg.serialize())

@bp.route("/logout/", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if request.method == "GET":
                return redirect(url_for("auth.login"))
            return redirect(url_for("auth.login"), code=303)
        return view(**kwargs)
    return wrapped_view

def role_required(view, required_role: str):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return "Forbidden", 403
        user_role = g.user.get("role")
        if user_role != required_role:
            return "Forbidden", 403
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    return role_required(view, "admin")

@click.command("create-auth-user")
@click.argument("email")
@click.argument("password")
@click.option("--admin", is_flag=True, default=False, help="Assign admin role.")
def create_auth_user(email: str, password: str, admin: bool) -> None:
    normalized_email = email.strip().lower()
    try:
        user = db.create_auth_user(normalized_email, password)
        role = "admin" if admin else "member"
        db.upsert_user_role(user.id, role)
        db.sync_default_role_group(user_id=user.id, role=role, created_by=user.id)
        click.echo(f"Created auth user: {normalized_email}")
    except Exception as exc:
        click.echo(f"Failed to create user: {exc}")

def setup(app):
    app.cli.add_command(create_auth_user)
