from datetime import date, datetime
import re

from flask import abort, Blueprint, g, redirect, render_template, request, url_for

from server import db, md, meta, models
from server.auth import login_required

bp = Blueprint("projects", __name__, url_prefix="/projects")

PROJECT_INDEX_COLUMNS = "id,title,summary,status,stack,published_at,started_on,ended_on,pinned,public,canonical_url"

def projects_visibility_filter() -> str:
    if g.user:
        return f"user_id.eq.{g.user['id']},public.eq.true"
    return "public.eq.true"

def visible_projects_query(columns: str = "*"):
    return db.get().table("projects").select(columns).or_(projects_visibility_filter())

def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None

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
        .order("published_at", desc=True)
        .execute()
    ).data
    for project in projects_data:
        project["published_at"] = datetime.fromisoformat(project["published_at"])
        project["started_on"] = date.fromisoformat(project["started_on"]) if project.get("started_on") else None
        project["ended_on"] = date.fromisoformat(project["ended_on"]) if project.get("ended_on") else None
        project["pinned"] = bool(project.get("pinned"))
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
    summary: str | None,
    content: str | None,
    started_on: str | None,
    ended_on: str | None,
    status: str | None,
    stack: str | None,
    project_url: str | None,
    repo_url: str | None,
    pinned: bool,
    public: bool,
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
        "summary": normalize_text(summary),
        "content": normalized_content,
        "html": content_to_html(normalized_content),
        "canonical_url": title_to_canonical(title),
        "status": normalize_text(status),
        "stack": normalize_text(stack),
        "project_url": normalize_text(project_url),
        "repo_url": normalize_text(repo_url),
        "pinned": pinned,
        "public": public,
    }
    response = (
        database.table("projects")
        .insert(project)
        .execute()
    ).data
    return response[0]["id"]

def update_project(
    id: int,
    title: str,
    summary: str | None,
    content: str | None,
    started_on: str | None,
    ended_on: str | None,
    status: str | None,
    stack: str | None,
    project_url: str | None,
    repo_url: str | None,
    pinned: bool,
    public: bool,
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
        "summary": normalize_text(summary),
        "content": normalized_content,
        "html": content_to_html(normalized_content),
        "canonical_url": title_to_canonical(title),
        "status": normalize_text(status),
        "stack": normalize_text(stack),
        "project_url": normalize_text(project_url),
        "repo_url": normalize_text(repo_url),
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
    return id

def delete_project(id: int) -> None:
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

    cfg = meta.Metadata()
    return render_template("projects/show.jinja", **cfg.serialize(), project=project)

@bp.route("/<string:name>/", methods=["GET"])
def show_canonical(name: str):
    project = get_project_by_url(name)
    if not project:
        abort(404)
    project.html = project.html or content_to_html(project.content)

    cfg = meta.Metadata()
    return render_template("projects/show.jinja", **cfg.serialize(), project=project)

@bp.route("/new/", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        summary = request.form.get("summary")
        content = request.form.get("content")
        started_on = request.form.get("started_on")
        ended_on = request.form.get("ended_on")
        status = request.form.get("status")
        stack = request.form.get("stack")
        project_url = request.form.get("project_url")
        repo_url = request.form.get("repo_url")
        pinned = "pinned" in request.form
        public = "public" in request.form

        id = create_project(
            title=title,
            summary=summary,
            content=content,
            started_on=started_on,
            ended_on=ended_on,
            status=status,
            stack=stack,
            project_url=project_url,
            repo_url=repo_url,
            pinned=pinned,
            public=public,
        )
        return redirect(url_for("projects.show_id", id=id))

    cfg = meta.Metadata()
    return render_template("projects/create.jinja", **cfg.serialize())

@bp.route("/<int:id>/edit/", methods=["GET", "POST"])
@login_required
def update(id: int):
    project = get_project_by_id(id)
    if not project:
        abort(404)

    if request.method == "POST":
        title = request.form["title"]
        summary = request.form.get("summary")
        content = request.form.get("content")
        started_on = request.form.get("started_on")
        ended_on = request.form.get("ended_on")
        status = request.form.get("status")
        stack = request.form.get("stack")
        project_url = request.form.get("project_url")
        repo_url = request.form.get("repo_url")
        pinned = "pinned" in request.form
        public = "public" in request.form

        id = update_project(
            id=id,
            title=title,
            summary=summary,
            content=content,
            started_on=started_on,
            ended_on=ended_on,
            status=status,
            stack=stack,
            project_url=project_url,
            repo_url=repo_url,
            pinned=pinned,
            public=public,
        )
        return redirect(url_for("projects.show_id", id=id))

    cfg = meta.Metadata()
    return render_template("projects/update.jinja", **cfg.serialize(), project=project)

@bp.route("/<int:id>/delete/", methods=["POST"])
@login_required
def delete(id: int):
    delete_project(id)
    return redirect(url_for("projects.index"))

@bp.route("/", methods=["GET"])
def index():
    projects = get_projects()

    cfg = meta.Metadata()
    return render_template("projects/index.jinja", **cfg.serialize(), projects=projects)
