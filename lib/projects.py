import markdown
from flask import (
    Blueprint, request, render_template, flash, redirect, url_for, g, abort, session
)

from lib.auth import login_required
from lib.db import query

from psycopg2.extras import RealDictRow

bp = Blueprint("projects", __name__, url_prefix="/projects")

FIELDS = ["name", "startdate", "enddate", "urlid", "link", "github", "brief", "content", "public", "pinned", "continuous"]

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
        urlid = request.form["urlid"] if request.form["urlid"] != "" else None
        link = request.form["link"] if request.form["link"] != "" else None
        github = request.form["github"] if request.form["github"] != "" else None
        brief = request.form["brief"] if request.form["brief"] != "" else None
        startdate = request.form["startdate"] if request.form["startdate"] != "" else None
        enddate = request.form["enddate"]  if request.form["enddate"] != "" else None
        content = request.form["content"] or "..."
        public = "public" in request.form
        pinned = "pinned" in request.form
        continuous = "continuous" in request.form
        if not name:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            query(
                f"INSERT INTO projects ({', '.join(FIELDS)}, author_id)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                args=[name, startdate, enddate, urlid, link, github, brief, content, public, pinned, continuous, g.user["id"]]
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
        urlid = request.form["urlid"] if request.form["urlid"] != "" else None
        link = request.form["link"] if request.form["link"] != "" else None
        github = request.form["github"] if request.form["github"] != "" else None
        brief = request.form["brief"] if request.form["brief"] != "" else None
        startdate = request.form["startdate"] if request.form["startdate"] != "" else None
        enddate = request.form["enddate"]  if request.form["enddate"] != "" else None
        content = request.form["content"] or "..."
        public = "public" in request.form
        pinned = "pinned" in request.form
        continuous = "continuous" in request.form
        if not name:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            query(
                f"UPDATE projects SET {', '.join([f'{x} = %s' for x in FIELDS])}"
                " WHERE ID = %s",
                args=[name, startdate, enddate, urlid, link, github, brief, content, public, pinned, continuous, id]
            )
            return redirect(url_for("projects.show_id", id=id))
    return render_template("projects/update.html", project=project)

@bp.route("/<int:id>", methods=["GET"])
def show_id(id):
    project = dict(get_project(id))
    if len(project) == 0:
        abort(404, description="Project not found.")
    if project["urlid"] != None:
        session["project"] = project
        return redirect(url_for("projects.show_name", name=project["urlid"]))
    project["content"] = markdown.markdown(project["content"], extensions=["fenced_code", "tables", "nl2br", "toc"])
    return render_template("projects/show.html", project=project, parent="projects.index", omitHeader=True)

@bp.route("/<string:name>", methods=["GET"])
def show_name(name):
    project = ("project" in session and session["project"]) or dict(get_project_by_name(name))
    session["project"] = None
    if len(project) == 0:
        abort(404, description="Project not found.")
    project["content"] = markdown.markdown(project["content"], extensions=["fenced_code", "tables", "nl2br", "toc"])
    return render_template("projects/show.html", project=project, parent="projects.index", omitHeader=True)

@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    query("DELETE FROM projects WHERE id = %s", args=[id])
    return redirect(url_for("projects.index"))

def get_project(id):
    return (query(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s AND (p.author_id = %s OR public IS TRUE)",
        args=[id, (g.user or {"id": None})["id"]]
    ) or [RealDictRow()])[0]


def get_project_by_name(name):
    return (query(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE p.urlid = %s AND (p.author_id = %s OR public IS TRUE)",
        args=[name, (g.user or {"id": None})["id"]]
    ) or [RealDictRow()])[0]

def get_projects():
    return query(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM projects p JOIN users u ON p.author_id = u.id"
        " WHERE public IS TRUE OR p.author_id = %s"
        " ORDER BY enddate DESC NULLS FIRST, startdate DESC",
        args=[(g.user or {"id": None})["id"]]
    )
