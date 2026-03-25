from datetime import date, datetime
import re

from flask import abort, Blueprint, current_app, g, redirect, render_template, request, url_for

from server import db, md, meta, models
from server.auth import login_required

bp = Blueprint("projects", __name__, url_prefix="/projects")

PROJECT_INDEX_COLUMNS = "id,title,deck,summary,status,stack,published_at,started_on,ended_on,pinned,research,public,canonical_url"

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

def _owner_id(record: models.Project | dict) -> str | None:
    if isinstance(record, models.Project):
        return record.user_id
    owner = record.get("user_id")
    return str(owner) if owner is not None else None

def can_manage_project(record: models.Project | dict) -> bool:
    if g.user is None:
        return False
    if _is_admin():
        return True
    owner_id = _owner_id(record)
    return owner_id == g.user["id"]

def visible_projects_query(columns: str = "*"):
    # RLS now enforces visibility, so we avoid extra prefilter queries.
    return db.get().table("projects").select(columns)

def get_project_record_by_id(id: int) -> dict | None:
    data = (
        db.get().table("projects")
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

def project_group_map(project_ids: list[int]) -> dict[int, list[str]]:
    if not project_ids:
        return {}
    return db.get_project_group_map(project_ids)

def normalize_content(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.strip():
        return None
    return value

def normalize_date(value: str | None) -> date | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None

def date_to_timestamp(value: date) -> str:
    return datetime.combine(value, datetime.min.time()).isoformat()

def title_to_canonical(title: str) -> str:
    url = title.lower().strip()
    url = re.sub(r"\s+", "-", url)
    url = url.replace("&", "-and-")
    url = re.sub(r"[^\w\-]+", "", url)
    url = re.sub(r"\-+", "-", url)
    return url

def content_to_html(content: str | None) -> str | None:
    if not content:
        return None
    return md.render(content)

def get_projects() -> list[dict]:
    projects_data = (
        visible_projects_query(PROJECT_INDEX_COLUMNS)
        .order("pinned", desc=True)
        .order("research", desc=True)
        .order("published_at", desc=True)
        .execute()
    ).data
    group_map = project_group_map([project["id"] for project in projects_data])
    for project in projects_data:
        project["published_at"] = datetime.fromisoformat(project["published_at"])
        project["started_on"] = date.fromisoformat(project["started_on"]) if project.get("started_on") else None
        project["ended_on"] = date.fromisoformat(project["ended_on"]) if project.get("ended_on") else None
        project["pinned"] = bool(project.get("pinned"))
        project["research"] = bool(project.get("research"))
        project["visibility_groups"] = group_map.get(project["id"], [])
    return projects_data

def get_project_by_id(id: int) -> models.Project | None:
    project_data = (
        visible_projects_query()
        .eq("id", id)
        .execute()
    ).data
    if project_data:
        return models.Project.from_dict(project_data[0])
    return None

def get_project_by_url(canonical_url: str) -> models.Project | None:
    project_data = (
        visible_projects_query()
        .eq("canonical_url", canonical_url)
        .execute()
    ).data
    if project_data:
        return models.Project.from_dict(project_data[0])
    return None

def create_project(
    title: str,
    deck: str | None,
    summary: str | None,
    content: str | None,
    started_on: str | None,
    ended_on: str | None,
    status: str | None,
    stack: str | None,
    project_url: str | None,
    repo_url: str | None,
    paper_url: str | None,
    research: bool,
    pinned: bool,
    public: bool,
    group_ids: list[int],
) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    normalized_content = normalize_content(content)
    normalized_started_on = normalize_date(started_on)
    normalized_ended_on = normalize_date(ended_on)
    project = {
        "created_at": now,
        "user_id": g.user["id"],
        "published_at": date_to_timestamp(normalized_started_on) if normalized_started_on else now,
        "updated_at": now,
        "started_on": normalized_started_on.isoformat() if normalized_started_on else None,
        "ended_on": normalized_ended_on.isoformat() if normalized_ended_on else None,
        "title": title,
        "deck": normalize_text(deck),
        "summary": normalize_text(summary),
        "content": normalized_content,
        "html": content_to_html(normalized_content),
        "canonical_url": title_to_canonical(title),
        "status": normalize_text(status),
        "stack": normalize_text(stack),
        "project_url": normalize_text(project_url),
        "repo_url": normalize_text(repo_url),
        "paper_url": normalize_text(paper_url),
        "research": research,
        "pinned": pinned,
        "public": public,
    }
    response = (
        database.table("projects")
        .insert(project)
        .execute()
    ).data
    project_id = response[0]["id"]
    db.replace_project_groups(project_id, group_ids)
    return project_id

def update_project(
    id: int,
    title: str,
    deck: str | None,
    summary: str | None,
    content: str | None,
    started_on: str | None,
    ended_on: str | None,
    status: str | None,
    stack: str | None,
    project_url: str | None,
    repo_url: str | None,
    paper_url: str | None,
    research: bool,
    pinned: bool,
    public: bool,
    group_ids: list[int],
) -> int:
    database = db.get()
    now = datetime.utcnow().isoformat()
    normalized_content = normalize_content(content)
    normalized_started_on = normalize_date(started_on)
    normalized_ended_on = normalize_date(ended_on)
    project = {
        "updated_at": now,
        "started_on": normalized_started_on.isoformat() if normalized_started_on else None,
        "ended_on": normalized_ended_on.isoformat() if normalized_ended_on else None,
        "title": title,
        "deck": normalize_text(deck),
        "summary": normalize_text(summary),
        "content": normalized_content,
        "html": content_to_html(normalized_content),
        "canonical_url": title_to_canonical(title),
        "status": normalize_text(status),
        "stack": normalize_text(stack),
        "project_url": normalize_text(project_url),
        "repo_url": normalize_text(repo_url),
        "paper_url": normalize_text(paper_url),
        "research": research,
        "pinned": pinned,
        "public": public,
    }
    if normalized_started_on:
        project["published_at"] = date_to_timestamp(normalized_started_on)
    (
        database.table("projects")
        .update(project)
        .eq("id", id)
        .execute()
    )
    db.replace_project_groups(id, group_ids)
    return id

def delete_project(id: int) -> None:
    db.replace_project_groups(id, [])
    database = db.get()
    (
        database.table("projects")
        .delete()
        .eq("id", id)
        .execute()
    )

@bp.route("/<int:id>/", methods=["GET"])
def show_id(id: int):
    project = get_project_by_id(id)
    if not project:
        abort(404)
    if project.canonical_url:
        return redirect(url_for("projects.show_canonical", name=project.canonical_url))
    project.html = project.html or content_to_html(project.content)
    needs_math = md.contains_math(project.content or project.html)
    groups = db.get_project_group_map([project.id]).get(project.id, [])

    cfg = meta.Metadata()
    return render_template(
        "projects/show.jinja",
        **cfg.serialize(),
        project=project,
        needs_math=needs_math,
        can_edit=can_manage_project(project),
        visibility_groups=groups,
    )

@bp.route("/<string:name>/", methods=["GET"])
def show_canonical(name: str):
    project = get_project_by_url(name)
    if not project:
        abort(404)
    project.html = project.html or content_to_html(project.content)
    needs_math = md.contains_math(project.content or project.html)
    groups = db.get_project_group_map([project.id]).get(project.id, [])

    cfg = meta.Metadata()
    return render_template(
        "projects/show.jinja",
        **cfg.serialize(),
        project=project,
        needs_math=needs_math,
        can_edit=can_manage_project(project),
        visibility_groups=groups,
    )

@bp.route("/new/", methods=["GET", "POST"])
@login_required
def create():
    available_groups, default_group_ids, show_group_selector = group_form_context_for_current_user()
    if request.method == "POST":
        title = request.form["title"]
        deck = request.form.get("deck")
        summary = request.form.get("summary")
        content = request.form.get("content")
        started_on = request.form.get("started_on")
        ended_on = request.form.get("ended_on")
        status = request.form.get("status")
        stack = request.form.get("stack")
        project_url = request.form.get("project_url")
        repo_url = request.form.get("repo_url")
        paper_url = request.form.get("paper_url")
        research = "research" in request.form
        pinned = "pinned" in request.form
        public = "public" in request.form
        group_ids = parse_allowed_group_ids(available_groups)
        if not group_ids and not show_group_selector:
            group_ids = default_group_ids.copy()

        id = create_project(
            title=title,
            deck=deck,
            summary=summary,
            content=content,
            started_on=started_on,
            ended_on=ended_on,
            status=status,
            stack=stack,
            project_url=project_url,
            repo_url=repo_url,
            paper_url=paper_url,
            research=research,
            pinned=pinned,
            public=public,
            group_ids=group_ids,
        )
        return redirect(url_for("projects.show_id", id=id))

    cfg = meta.Metadata()
    return render_template(
        "projects/create.jinja",
        **cfg.serialize(),
        available_groups=available_groups,
        selected_group_ids=[str(group_id) for group_id in default_group_ids],
        show_group_selector=show_group_selector,
    )

@bp.route("/<int:id>/edit/", methods=["GET", "POST"])
@login_required
def update(id: int):
    project_record = get_project_record_by_id(id)
    if not project_record:
        abort(404)
    project = models.Project.from_dict(project_record)
    if not can_manage_project(project):
        current_app.logger.warning(
            "Project manage denied: project_id=%s user_id=%s owner_id=%s is_admin=%s",
            id,
            g.user["id"] if g.user else None,
            project.user_id,
            _is_admin(),
        )
        abort(403)
    available_groups, default_group_ids, show_group_selector = group_form_context_for_current_user()
    existing_group_ids = db.get_project_group_ids(id)

    if request.method == "POST":
        title = request.form["title"]
        deck = request.form.get("deck")
        summary = request.form.get("summary")
        content = request.form.get("content")
        started_on = request.form.get("started_on")
        ended_on = request.form.get("ended_on")
        status = request.form.get("status")
        stack = request.form.get("stack")
        project_url = request.form.get("project_url")
        repo_url = request.form.get("repo_url")
        paper_url = request.form.get("paper_url")
        research = "research" in request.form
        pinned = "pinned" in request.form
        public = "public" in request.form
        group_ids = parse_allowed_group_ids(available_groups)
        if not group_ids and not show_group_selector:
            group_ids = existing_group_ids.copy() if existing_group_ids else default_group_ids.copy()

        id = update_project(
            id=id,
            title=title,
            deck=deck,
            summary=summary,
            content=content,
            started_on=started_on,
            ended_on=ended_on,
            status=status,
            stack=stack,
            project_url=project_url,
            repo_url=repo_url,
            paper_url=paper_url,
            research=research,
            pinned=pinned,
            public=public,
            group_ids=group_ids,
        )
        return redirect(url_for("projects.show_id", id=id))

    selected_group_ids = [str(group_id) for group_id in existing_group_ids]
    if not selected_group_ids:
        selected_group_ids = [str(group_id) for group_id in default_group_ids]
    cfg = meta.Metadata()
    return render_template(
        "projects/update.jinja",
        **cfg.serialize(),
        project=project,
        available_groups=available_groups,
        selected_group_ids=selected_group_ids,
        show_group_selector=show_group_selector,
    )

@bp.route("/<int:id>/delete/", methods=["POST"])
@login_required
def delete(id: int):
    project_record = get_project_record_by_id(id)
    if not project_record:
        abort(404)
    project = models.Project.from_dict(project_record)
    if not can_manage_project(project):
        current_app.logger.warning(
            "Project delete denied: project_id=%s user_id=%s owner_id=%s is_admin=%s",
            id,
            g.user["id"] if g.user else None,
            project.user_id,
            _is_admin(),
        )
        abort(403)
    delete_project(id)
    return redirect(url_for("projects.index"))

@bp.route("/", methods=["GET"])
def index():
    projects = get_projects()

    cfg = meta.Metadata()
    return render_template("projects/index.jinja", **cfg.serialize(), projects=projects)
