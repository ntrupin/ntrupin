import markdown
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

@bp.route("/<int:id>/update", methods=["GET", "POST"])
@login_required
def update(id):
    project = get_project(id)
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
                "UPDATE projects SET name = %s, startdate = %s, enddate = %s, content = %s, public = %s"
                " WHERE ID = %s",
                args=[name, startdate, enddate, content, public, id]
            )
            return redirect(url_for("projects.show", id=id))
    return render_template("projects/update.html", project=project)

@bp.route("/<int:id>", methods=["GET"])
def show(id):
    project = dict(get_project(id))
    project["content"] = markdown.markdown(project["content"], extensions=["fenced_code", "tables", "nl2br", "toc"])
    return render_template("projects/show.html", project=project)

@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    execute("DELETE FROM projects WHERE id = %s", args=[id])
    return redirect(url_for("projects.index"))

def get_project(id):
    return execute(
        "SELECT p.id, name, startdate, enddate, content, public, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s AND public IN %s",
        args=[id, (True,) if g.user is None else (True, False)]
    )[0]

def get_projects():
    return execute(
        "SELECT p.id, name, startdate, enddate, content, public, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE public IS TRUE"
        " ORDER BY enddate DESC NULLS FIRST, startdate DESC"
    )