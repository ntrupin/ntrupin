import functools

import click
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from noah import db, meta

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.before_app_request
def load_logged_in_user():
    user = session.get("user")
    g.user = user

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = db.get_user(username)
        if not user or not check_password_hash(user["password"], password):
            flash("Incorrect username or password")
            return redirect(url_for("auth.login"))

        session.clear()
        session["user"] = user
        return redirect(url_for("index"))

    cfg = meta.Metadata()
    cfg.title = "Login"
    return render_template("auth/login.jinja", **cfg.serialize())

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return "Forbidden", 403
        return view(**kwargs)
    return wrapped_view

@click.command("add-user")
@click.argument("username")
@click.argument("password")
def add_user(username: str, password: str) -> None:
    existing_user = db.get_user(username)
    if existing_user:
        click.echo(f"User {username} already exists.")
        return
    hashed_password = generate_password_hash(password)
    db.insert_user(username, hashed_password)
    click.echo(f"User {username} added.")

def setup(app):
    app.cli.add_command(add_user)
