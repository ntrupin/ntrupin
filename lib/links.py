import datetime
from flask import (
    Blueprint, render_template, g, redirect, url_for, flash,
    request
)

from lib.auth import login_required
from lib.db import query

from psycopg2.extras import RealDictRow

bp = Blueprint("links", __name__, url_prefix="/reading_list")

FIELDS = ["text", "url", "pinned"]

@bp.route("/")
def index():
    links = get_links()
    cutoff = datetime.datetime(2024, 6, 26)
    return render_template("links/index.html", links=links, cutoff=cutoff)

@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        error = None
        text = request.form["text"]
        url = request.form["url"]
        pinned = "pinned" in request.form

        if not text or not url:
            error = "Field is required"
        if error is not None:
            flash(error)
        else:
            query(
                f"INSERT INTO links ({', '.join(FIELDS)}, author_id)"
                " VALUES (%s, %s, %s, %s)",
                args=[text, url, pinned, g.user["id"]]
            )
            return redirect(url_for("links.index"))

    return render_template("links/create.html")

@bp.route("/<int:id>/update", methods=["GET", "POST"])
@login_required
def update(id):
    link = get_link_by_id(id)
    if request.method == "POST":
        error = None
        text = request.form["text"]
        url = request.form["url"]
        pinned = "pinned" in request.form

        if not text or not url:
            error = "Name is required"
        if error is not None:
            flash(error)
        else:
            query(
                f"UPDATE links SET {', '.join([f'{x} = %s' for x in FIELDS])}"
                " WHERE ID = %s",
                args=[text, url, pinned, id]
            )
            return redirect(url_for("links.index"))

    return render_template("links/update.html", link=link)

@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    query("DELETE FROM links WHERE id = %s", args=[id])
    return redirect(url_for("links.index"))

def get_link_by_id(id):
    return (query(
        f"SELECT id, {', '.join(FIELDS)}, created, author_id"
        " FROM links WHERE id = %s",
        args=[id]
    ) or [RealDictRow()])[0]

def get_links():
    return query(
        f"SELECT id, {', '.join(FIELDS)}, created, author_id"
        " FROM links ORDER BY created DESC",
        args=[(g.user or {"id": None})["id"]]
    )
