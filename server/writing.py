from datetime import datetime
import re

from flask import abort, Blueprint, redirect, render_template, request, url_for

from server import db, md, meta, models
from server.auth import login_required

bp = Blueprint("writing", __name__, url_prefix="/writing")

def get_writing_by_id(id: int) -> models.Writing | None:
    database = db.get()
    writing_data = (
        database.table("writing")
        .select("*")
        .eq("id", id)
        .execute()
    ).data
    if writing_data:
        return models.Writing.from_dict(writing_data[0])
    return None

def get_writing_by_url(canonical_url: str) -> models.Writing | None:
    database = db.get()
    writing_data = (
        database.table("writing")
        .select("*")
        .eq("canonical_url", canonical_url)
        .execute()
    ).data
    if writing_data:
        return models.Writing.from_dict(writing_data[0])
    return None

def title_to_canonical(title: str) -> str:
    url = title.lower().strip()
    url = re.sub(r"\s+", "-", url)
    url = url.replace("&", "-and-")
    url = re.sub(r"[^\w\-]+", "", url)
    url = re.sub(r"\-+", "-", url)
    return url

def create_writing(title: str, content: str | None, public: bool) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    writing = {
        "created_at": now,
        "user_id": 1,
        "published_at": now if public else None,
        "updated_at": now,
        "title": title,
        "content": content,
        "canonical_url": title_to_canonical(title),
        "public": public,
    }
    response = (
        database.table("writing")
        .insert(writing)
        .execute()
    ).data
    return response[0]["id"]

def update_writing(id: int, title: str, content: str | None, public: bool) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    writing = {
        "updated_at": now,
        "title": title,
        "content": content,
        "canonical_url": title_to_canonical(title),
        "public": public,
    }
    #if public:
    #    writing["published_at"] = now
    (
        database.table("writing")
        .update(writing)
        .eq("id", id)
        .execute()
    )
    return id

def delete_writing(id: int) -> None:
    database = db.get()
    (
        database.table("writing")
        .delete()
        .eq("id", id)
        .execute()
    )

@bp.route("/<int:id>/", methods=["GET"])
def show_id(id: int):
    writing = get_writing_by_id(id)
    if not writing:
        abort(404)
    if writing.canonical_url:
        return redirect(url_for("writing.show_canonical", name=writing.canonical_url))
    writing.content = md.render(writing.content or "Nothing to see here.")

    cfg = meta.Metadata()
    return render_template("writing/show.jinja", **cfg.serialize(), writing=writing)

@bp.route("/<string:name>/", methods=["GET"])
def show_canonical(name: str):
    writing = get_writing_by_url(name)
    if not writing:
        abort(404)
    writing.content = md.render(writing.content or "Nothing to see here.")

    cfg = meta.Metadata()
    return render_template("writing/show.jinja", **cfg.serialize(), writing=writing)

@bp.route("/new/", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form.get("content")
        public = "public" in request.form

        id = create_writing(title, content, public)
        return redirect(url_for("writing.show_id", id=id))

    cfg = meta.Metadata()
    return render_template("writing/create.jinja", **cfg.serialize())

@bp.route("/<int:id>/edit/", methods=["GET", "POST"])
@login_required
def update(id: int):
    writing = get_writing_by_id(id)
    if not writing:
        abort(404)

    if request.method == "POST":

        title = request.form["title"]
        content = request.form.get("content")
        public = "public" in request.form

        id = update_writing(id, title, content, public)
        return redirect(url_for("writing.show_id", id=id))

    cfg = meta.Metadata()
    return render_template("writing/update.jinja", **cfg.serialize(), writing=writing)

@bp.route("/<int:id>/delete/", methods=["POST"])
@login_required
def delete(id: int):
    delete_writing(id)
    return redirect(url_for("index"))
