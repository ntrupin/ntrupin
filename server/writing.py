from datetime import datetime
import re

from flask import abort, Blueprint, current_app, g, redirect, render_template, request, url_for

from server import db, md, meta, models
from server.auth import login_required

bp = Blueprint("writing", __name__, url_prefix="/writing")

WRITING_INDEX_COLUMNS = "id,title,summary,pinned,published_at,public,canonical_url"

def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None

def _group_ids_for_current_user() -> list[int]:
    if not g.user:
        return []
    return [int(group_id) for group_id in g.user.get("group_ids", [])]

def _is_admin() -> bool:
    return bool(g.user and g.user.get("is_admin"))

def _owner_id(record: models.Writing | dict) -> str | None:
    if isinstance(record, models.Writing):
        return record.user_id
    owner = record.get("user_id")
    return str(owner) if owner is not None else None

def can_manage_writing(record: models.Writing | dict) -> bool:
    if g.user is None:
        return False
    if _is_admin():
        return True
    owner_id = _owner_id(record)
    return owner_id == g.user["id"]

def visible_writing_query(columns: str = "*"):
    query = db.get().table("writing").select(columns)
    # Defense-in-depth: never expose private writing to anonymous sessions.
    if g.user is None:
        query = query.eq("public", True)
    return query

def get_writing_record_by_id(id: int) -> dict | None:
    data = (
        db.get().table("writing")
        .select("*")
        .eq("id", id)
        .limit(1)
        .execute()
    ).data
    return data[0] if data else None

def group_form_context_for_current_user() -> tuple[list[dict], list[int], bool]:
    if not g.user:
        return [], [], False

    if _is_admin():
        available_groups = db.list_groups()
    else:
        available_groups = db.list_groups_by_ids(_group_ids_for_current_user())

    if available_groups:
        return available_groups, [], len(available_groups) > 1

    default_group = db.ensure_default_role_group(
        user_id=g.user["id"],
        is_admin=_is_admin(),
    )
    if not default_group:
        return [], [], False

    g.user["group_ids"] = db.get_user_group_ids(g.user["id"])
    default_group_id = int(default_group["id"])
    return [default_group], [default_group_id], False

def parse_allowed_group_ids(available_groups: list[dict]) -> list[int]:
    allowed_group_ids = {int(group["id"]) for group in available_groups}
    selected: list[int] = []
    for raw_group_id in request.form.getlist("group_ids"):
        try:
            parsed = int(raw_group_id)
        except ValueError:
            continue
        if parsed in allowed_group_ids:
            selected.append(parsed)
    return sorted(set(selected))

def writing_group_map(writing_ids: list[int]) -> dict[int, list[str]]:
    if not writing_ids:
        return {}
    return db.get_writing_group_map(writing_ids)

def get_writings() -> list[dict]:
    writings_data = (
        visible_writing_query(WRITING_INDEX_COLUMNS)
        .order("pinned", desc=True)
        .order("published_at", desc=True)
        .execute()
    ).data
    group_map = writing_group_map([writing["id"] for writing in writings_data])
    for writing in writings_data:
        writing["published_at"] = datetime.fromisoformat(writing["published_at"])
        writing["pinned"] = bool(writing.get("pinned"))
        writing["visibility_groups"] = group_map.get(writing["id"], [])
    return writings_data

def get_writing_by_id(id: int) -> models.Writing | None:
    writing_data = (
        visible_writing_query()
        .eq("id", id)
        .execute()
    ).data
    if writing_data:
        return models.Writing.from_dict(writing_data[0])
    return None

def get_writing_by_url(canonical_url: str) -> models.Writing | None:
    writing_data = (
        visible_writing_query()
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

def content_to_html(content: str | None) -> str:
    return md.render(content or "Nothing to see here.")

def create_writing(
    title: str,
    summary: str | None,
    content: str | None,
    pinned: bool,
    public: bool,
    group_ids: list[int],
) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    writing = {
        "created_at": now,
        "user_id": g.user["id"],
        "published_at": now,
        "updated_at": now,
        "title": title,
        "summary": normalize_text(summary),
        "content": content,
        "html": content_to_html(content),
        "canonical_url": title_to_canonical(title),
        "pinned": pinned,
        "public": public,
    }
    response = (
        database.table("writing")
        .insert(writing)
        .execute()
    ).data
    writing_id = response[0]["id"]
    db.replace_writing_groups(writing_id, group_ids)
    return writing_id

def update_writing(
    id: int,
    title: str,
    summary: str | None,
    content: str | None,
    pinned: bool,
    public: bool,
    group_ids: list[int],
) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    writing = {
        "updated_at": now,
        "title": title,
        "summary": normalize_text(summary),
        "content": content,
        "html": content_to_html(content),
        "canonical_url": title_to_canonical(title),
        "pinned": pinned,
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
    db.replace_writing_groups(id, group_ids)
    return id

def delete_writing(id: int) -> None:
    db.replace_writing_groups(id, [])
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
    writing.html = writing.html or content_to_html(writing.content)
    needs_math = md.contains_math(writing.content or writing.html)
    groups = db.get_writing_group_map([writing.id]).get(writing.id, [])

    cfg = meta.Metadata()
    return render_template(
        "writing/show.jinja",
        **cfg.serialize(),
        writing=writing,
        needs_math=needs_math,
        can_edit=can_manage_writing(writing),
        visibility_groups=groups,
    )

@bp.route("/<string:name>/", methods=["GET"])
def show_canonical(name: str):
    writing = get_writing_by_url(name)
    if not writing:
        abort(404)
    writing.html = writing.html or content_to_html(writing.content)
    needs_math = md.contains_math(writing.content or writing.html)
    groups = db.get_writing_group_map([writing.id]).get(writing.id, [])

    cfg = meta.Metadata()
    return render_template(
        "writing/show.jinja",
        **cfg.serialize(),
        writing=writing,
        needs_math=needs_math,
        can_edit=can_manage_writing(writing),
        visibility_groups=groups,
    )

@bp.route("/new/", methods=["GET", "POST"])
@login_required
def create():
    available_groups, default_group_ids, show_group_selector = group_form_context_for_current_user()
    if request.method == "POST":
        title = request.form["title"]
        summary = request.form.get("summary")
        content = request.form.get("content")
        pinned = "pinned" in request.form
        public = "public" in request.form
        group_ids = parse_allowed_group_ids(available_groups)
        if not group_ids and not show_group_selector:
            group_ids = default_group_ids.copy()

        id = create_writing(title, summary, content, pinned, public, group_ids)
        return redirect(url_for("writing.show_id", id=id))

    cfg = meta.Metadata()
    return render_template(
        "writing/create.jinja",
        **cfg.serialize(),
        available_groups=available_groups,
        selected_group_ids=[str(group_id) for group_id in default_group_ids],
        show_group_selector=show_group_selector,
    )

@bp.route("/<int:id>/edit/", methods=["GET", "POST"])
@login_required
def update(id: int):
    writing_record = get_writing_record_by_id(id)
    if not writing_record:
        abort(404)
    writing = models.Writing.from_dict(writing_record)
    if not can_manage_writing(writing):
        current_app.logger.warning(
            "Writing manage denied: writing_id=%s user_id=%s owner_id=%s is_admin=%s",
            id,
            g.user["id"] if g.user else None,
            writing.user_id,
            _is_admin(),
        )
        abort(403)
    available_groups, default_group_ids, show_group_selector = group_form_context_for_current_user()
    existing_group_ids = db.get_writing_group_ids(id)

    if request.method == "POST":
        title = request.form["title"]
        summary = request.form.get("summary")
        content = request.form.get("content")
        pinned = "pinned" in request.form
        public = "public" in request.form
        group_ids = parse_allowed_group_ids(available_groups)
        if not group_ids and not show_group_selector:
            group_ids = existing_group_ids.copy() if existing_group_ids else default_group_ids.copy()

        id = update_writing(id, title, summary, content, pinned, public, group_ids)
        return redirect(url_for("writing.show_id", id=id))

    selected_group_ids = [str(group_id) for group_id in existing_group_ids]
    if not selected_group_ids:
        selected_group_ids = [str(group_id) for group_id in default_group_ids]
    cfg = meta.Metadata()
    return render_template(
        "writing/update.jinja",
        **cfg.serialize(),
        writing=writing,
        available_groups=available_groups,
        selected_group_ids=selected_group_ids,
        show_group_selector=show_group_selector,
    )

@bp.route("/<int:id>/delete/", methods=["POST"])
@login_required
def delete(id: int):
    writing_record = get_writing_record_by_id(id)
    if not writing_record:
        abort(404)
    writing = models.Writing.from_dict(writing_record)
    if not can_manage_writing(writing):
        current_app.logger.warning(
            "Writing delete denied: writing_id=%s user_id=%s owner_id=%s is_admin=%s",
            id,
            g.user["id"] if g.user else None,
            writing.user_id,
            _is_admin(),
        )
        abort(403)
    delete_writing(id)
    return redirect(url_for("index"))

@bp.route("/", methods=["GET"])
def index():
    writings = get_writings()

    cfg = meta.Metadata()
    return render_template("writing/index.jinja", **cfg.serialize(), writings=writings)
