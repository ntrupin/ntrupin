from datetime import datetime

from flask import abort, Blueprint, redirect, render_template, request, url_for
from markdown import markdown

from noah import db, meta, models
from noah.auth import login_required

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
        "canonical_url": None,
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

@bp.route("/<int:id>", methods=["GET"])
def show_id(id: int):
    writing = get_writing_by_id(id)
    if not writing:
        abort(404)
    if writing.canonical_url:
        return redirect(url_for("writing.show_canonical", name=writing.canonical_url))
    writing.content = markdown(writing.content or "Nothing to see here.")

    cfg = meta.Metadata()
    return render_template("writing/show.jinja", **cfg.serialize(), writing=writing)

@bp.route("/<string:canonical>", methods=["GET"])
def show_canonical(canonical: str):
    writing = get_writing_by_url(canonical)
    if not writing:
        abort(404)
    writing.content = markdown.markdown(writing.content or "Nothing to see here.")

    cfg = meta.Metadata()
    return render_template("writing/show.jinja", **cfg.serialize(), writings=writing)

@bp.route("/new", methods=["GET", "POST"])
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

@bp.route("/<int:id>/edit", methods=["GET", "POST"])
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

@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id: int):
    delete_writing(id)
    return redirect(url_for("index"))
