import functools

import click
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from server import db, meta

bp = Blueprint("auth", __name__, url_prefix="/auth")

SESSION_ACCESS_TOKEN_KEY = "sb_access_token"
SESSION_REFRESH_TOKEN_KEY = "sb_refresh_token"

def _clear_supabase_session() -> None:
    session.pop(SESSION_ACCESS_TOKEN_KEY, None)
    session.pop(SESSION_REFRESH_TOKEN_KEY, None)

def _session_tokens() -> tuple[str | None, str | None]:
    return (
        session.get(SESSION_ACCESS_TOKEN_KEY),
        session.get(SESSION_REFRESH_TOKEN_KEY),
    )

def _load_user_from_session():
    access_token, refresh_token = _session_tokens()
    if not access_token:
        return None

    auth_client = db.get().auth
    user = None

    try:
        user_response = auth_client.get_user(access_token)
        user = user_response.user if user_response else None
    except Exception:
        user = None

    if user is not None:
        return user

    if not refresh_token:
        return None

    try:
        refreshed = auth_client.refresh_session(refresh_token)
    except Exception:
        return None

    refreshed_session = refreshed.session
    if not refreshed_session:
        return None

    session[SESSION_ACCESS_TOKEN_KEY] = refreshed_session.access_token
    session[SESSION_REFRESH_TOKEN_KEY] = refreshed_session.refresh_token
    db.get().postgrest.auth(refreshed_session.access_token)
    return refreshed.user or refreshed_session.user

@bp.before_app_request
def load_logged_in_user():
    g.user = None
    auth_user = _load_user_from_session()
    if not auth_user:
        _clear_supabase_session()
        return

    user_email = (auth_user.email or "").strip().lower()
    role: str | None = None
    group_ids: list[int] = []

    # Keep one or more emails configured in SUPABASE_ADMIN_EMAILS auto-promoted.
    try:
        db.bootstrap_admin_role(auth_user.id, user_email)
        role = db.get_user_role(auth_user.id)
        group_ids = db.get_user_group_ids(auth_user.id)
    except Exception:
        role = None
        group_ids = []

    is_admin = role == "admin" or db.is_bootstrap_admin_email(user_email)
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
            return "Forbidden", 403
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
