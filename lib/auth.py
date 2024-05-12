import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
import click

import lib.db as ldb
from lib.db import query

bp = Blueprint("auth", __name__, url_prefix="/auth")

# register a new user
@click.command("add-user")
@click.argument("username")
@click.argument("password")
def add_user_command(username, password):
    db = ldb.get()
    try:
        query(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            args=[username, generate_password_hash(password)]
        )
    except db.IntegrityError:
        click.echo(f"User {username} is already registered.")
    else:
        click.echo(f"Successfully added {username} to database.")

# on get, render login
# on post, process provided information
@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None
        user = (query(
            "SELECT * FROM users WHERE username = %s", 
            args=[username]
        ) + [None])[0]
        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash(error)

    return render_template("auth/login.html")

# check if user logged in
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = query(
            "SELECT * FROM users WHERE id = %s", 
            args=[user_id]
        )[0]

# log out, clear session
@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# helper decorator, protect view
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view

def setup(app):
    app.cli.add_command(add_user_command)
