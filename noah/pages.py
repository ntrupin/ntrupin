import markdown
from flask import (
    Blueprint, render_template, g, abort, redirect, url_for, flash, request, abort
)

from noah.auth import login_required
from noah.db import execute

from psycopg2.extras import RealDictRow

bp = Blueprint("pages", __name__, url_prefix="/pages")

FIELDS = ["name", "content", "public"]

@bp.route("/")
@login_required
def index():
    pages = get_pages()
    return render_template("pages/index.html", pages=pages)

@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        error = None
        name = request.form["name"]
        content = request.form["content"] or "Nothing here yet."
        public = "public" in request.form

        if not name:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            execute(
                f"INSERT INTO pages ({', '.join(FIELDS)}, author_id)"
                " VALUES (%s, %s, %s, %s)",
                args=[name, content, public, g.user["id"]]
            )
            return redirect(url_for("pages.index"))

    return render_template("pages/create.html")

@bp.route("/<int:id>/update", methods=["GET", "POST"])
@login_required
def update(id):
    page = get_page(id)
    if request.method == "POST":
        error = None
        name = request.form["name"]
        content = request.form["content"] or "Nothing here yet."
        public = "public" in request.form

        if not name:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            execute(
                f"UPDATE pages SET {', '.join([f'{x} = %s' for x in FIELDS])}"
                " WHERE ID = %s",
                args=[name, content, public, id]
            )
            return redirect(url_for("pages.show_id", id=id))

    return render_template("pages/update.html", page=page)

@bp.route("/<int:id>", methods=["GET"])
def show_id(id):
    page = dict(get_page(id))
    if len(page) == 0:
        abort(404, description="Page not found.")
    page["content"] = markdown.markdown(page["content"], extensions=["fenced_code", "tables", "nl2br", "toc"])
    return render_template("pages/show.html", page=page)

@bp.route("/<string:name>", methods=["GET"])
def show_name(name):
    page = dict(get_page_by_fuzzy_name(name))
    if len(page) == 0:
        abort(404, description="Page not found.")
    page["content"] = markdown.markdown(page["content"], extensions=["fenced_code", "tables", "nl2br", "toc"])
    return render_template("pages/show.html", page=page)

@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    execute("DELETE FROM pages WHERE id = %s", args=[id])
    return redirect(url_for("pages.index"))

def get_page(id):
    return (execute(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM pages p JOIN users u ON p.author_id = u.id"
        " WHERE p.id = %s AND (p.author_id = %s OR public IS TRUE)",
        args=[id, (g.user or {"id": None})["id"]]
    ) or [RealDictRow()])[0]

def get_page_by_fuzzy_name(name):
    return (execute(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM pages p JOIN users u ON p.author_id = u.id"
        " WHERE p.name ilike %s AND (p.author_id = %s OR public IS TRUE)",
        args=[name, (g.user or {"id": None})["id"]]
    ) or [RealDictRow()])[0]

def get_pages():
    return execute(
        f"SELECT p.id, {', '.join(FIELDS)}, created, author_id, username"
        " FROM pages p JOIN users u ON p.author_id = u.id"
        " WHERE public IS TRUE OR p.author_id = %s",
        args=[(g.user or {"id": None})["id"]]
    )
