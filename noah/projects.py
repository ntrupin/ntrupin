from flask import (
    Blueprint, request, render_template, flash, redirect, url_for, g
)

from noah.auth import login_required
from noah.db import execute

bp = Blueprint("projects", __name__, url_prefix="/projects")

@bp.route("/")
def index():
    projects = get_projects()
    return render_template("projects/index.html", projects=projects)

@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        error = None
        name = request.form["name"]
        startdate = request.form["startdate"] if request.form["startdate"] != "" else None
        enddate = request.form["enddate"]  if request.form["enddate"] != "" else None
        content = request.form["content"] or "..."
        public = "public" in request.form
        if not name:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            print(g.user["id"])
            execute(
                "INSERT INTO projects (name, startdate, enddate, content, public, author_id)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                args=[name, startdate, enddate, content, public, g.user["id"]]
            )
            return redirect(url_for("projects.index"))
    return render_template("projects/create.html")

def get_projects():
    return execute(
        "SELECT p.id, name, startdate, enddate, content, public, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE public IS TRUE"
        " ORDER BY enddate DESC NULLS FIRST, startdate DESC"
    )