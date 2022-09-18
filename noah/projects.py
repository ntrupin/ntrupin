from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, current_app
)
from werkzeug.exceptions import abort
import markdown
import markdown.extensions.fenced_code
import markdown.extensions.tables
import markdown.extensions.nl2br

from noah.auth import login_required
from noah.db import get_db, execute, Count

bp = Blueprint("projects", __name__, url_prefix="/projects")

@bp.route("/")
def index():
    projects = execute(
        "SELECT p.id, name, startdate, enddate, link, about, langs, deps, platforms, images, public, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE public IN %s"
        " ORDER BY enddate DESC NULLS FIRST, startdate DESC",
        args=((True,) if g.user is None else (True, False),),
        retmode=Count.ALL
    )
    return render_template("projects/index.html", projects=projects)

@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    if request.method == "POST":
        error = None
        name = request.form["name"]
        startdate = request.form["startdate"]
        enddate = request.form["enddate"] if request.form["enddate"] else None
        link = request.form["link"]
        langs = request.form.getlist("langs[]")
        deps = request.form.getlist("deps[]")
        platforms = request.form.getlist("platforms[]")
        images = request.files.getlist("images[]")
        about = request.form["about"]
        public = "public" in request.form
        if not name:
            error = "Name is required."
        if error is not None:
            flash(error)
        else:
            execute(
                "INSERT INTO projects (name, startdate, enddate, link, langs, deps, platforms, images, about, public, author_id)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                args=(name, startdate, enddate, link, langs, deps, platforms, [], about, public, g.user["id"])
            )
            return redirect(url_for("projects.index"))

    return render_template("projects/create.html")

def get_project(id, check_author=True):
    project = execute(
        "SELECT p.id, name, startdate, enddate, link, about, langs, deps, platforms, images, public, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s AND public IN %s",
        args=(id, (True,) if g.user is None else (True, False)),
        retmode=Count.ONE
    )
    if project is None:
        abort(404, f"Project with id {id} does not exist.")
    if check_author and project["author_id"] != g.user["id"]:
        abort(403)
    return project

@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    project = get_project(id)
    if request.method == "POST":
        name = request.form["name"]
        startdate = request.form["startdate"]
        enddate = request.form["enddate"] if request.form["enddate"] else None
        link = request.form["link"]
        langs = request.form.getlist("langs[]")
        deps = request.form.getlist("deps[]")
        platforms = request.form.getlist("platforms[]")
        images = request.files.getlist("images[]")
        about = request.form["about"]
        public = "public" in request.form
        error = None
        if not name:
            error = "Title is required"
        if error is not None:
            flash(error)
        else:
            execute(
                "UPDATE projects SET name = %s, startdate = %s, enddate = %s, link = %s, langs = %s, deps = %s, platforms = %s, images = %s, about = %s, public = %s"
                " WHERE ID = %s",
                args=(name, startdate, enddate, link, langs, deps, platforms, [], about, public, id)
            )
            return redirect(url_for("projects.show", id=id))

    return render_template("projects/update.html", project=project)

@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    get_project(id)
    execute("DELETE FROM projects WHERE id = %s", args=(id,))
    return redirect(url_for("projects.index"))

@bp.route("/<int:id>", methods=("GET",))
def show(id):
    project = dict(get_project(id, False))
    project["about"] = markdown.markdown(project["about"], extensions=["fenced_code", "tables", "nl2br"])
    return render_template("projects/show.html", project=project)