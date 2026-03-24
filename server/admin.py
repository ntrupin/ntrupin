import re

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from server import db, meta
from server.auth import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^a-z0-9\-]+", "", normalized)
    normalized = re.sub(r"\-+", "-", normalized).strip("-")
    return normalized

def _admin_context() -> dict:
    users = db.list_auth_users(page=1, per_page=1000)
    roles = {row["user_id"]: row["role"] for row in db.list_roles()}
    groups = db.list_groups()
    memberships = db.list_group_memberships()

    users_by_id = {
        user.id: {
            "id": user.id,
            "email": user.email or "(no email)",
            "role": roles.get(user.id, "member"),
            "created_at": user.created_at,
            "last_sign_in_at": user.last_sign_in_at,
        }
        for user in users
    }
    groups_by_id = {group["id"]: group for group in groups}
    members_by_group: dict[int, list[dict]] = {group["id"]: [] for group in groups}
    for membership in memberships:
        group_id = membership["group_id"]
        group = groups_by_id.get(group_id)
        user = users_by_id.get(membership["user_id"])
        if not group or not user:
            continue
        members_by_group.setdefault(group_id, []).append(user)

    for group_id, members in members_by_group.items():
        members_by_group[group_id] = sorted(members, key=lambda m: m["email"].lower())

    return {
        "users": sorted(users_by_id.values(), key=lambda u: u["email"].lower()),
        "groups": groups,
        "members_by_group": members_by_group,
    }

@bp.route("/", methods=["GET"])
@admin_required
def index():
    cfg = meta.Metadata(title="Admin | Noah Trupin")
    return render_template(
        "admin/index.jinja",
        **cfg.serialize(),
        **_admin_context(),
    )

@bp.route("/users/create/", methods=["POST"])
@admin_required
def create_user():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    if not email or not password:
        flash("Email and password are required.")
        return redirect(url_for("admin.index"))

    try:
        user = db.create_auth_user(email, password)
        if is_admin:
            role = "admin"
        else:
            role = "member"
        db.upsert_user_role(user.id, role)
        db.sync_default_role_group(user_id=user.id, role=role, created_by=g.user["id"])
        flash(f"Created user {email}.")
    except Exception as exc:
        flash(f"Failed to create user: {exc}")
    return redirect(url_for("admin.index"))

@bp.route("/users/role/", methods=["POST"])
@admin_required
def update_role():
    user_id = request.form.get("user_id", "").strip()
    role = request.form.get("role", "member").strip().lower()
    if role not in {"member", "admin"}:
        flash("Invalid role.")
        return redirect(url_for("admin.index"))

    try:
        db.upsert_user_role(user_id, role)
        db.sync_default_role_group(user_id=user_id, role=role, created_by=g.user["id"])
        flash("Updated user role.")
    except Exception as exc:
        flash(f"Failed to update role: {exc}")
    return redirect(url_for("admin.index"))

@bp.route("/groups/create/", methods=["POST"])
@admin_required
def create_group():
    name = request.form.get("name", "").strip()
    explicit_slug = request.form.get("slug", "").strip().lower()
    slug = explicit_slug or slugify(name)

    if not name or not slug:
        flash("Group name and slug are required.")
        return redirect(url_for("admin.index"))

    try:
        db.create_group(name=name, slug=slug, created_by=g.user["id"])
        flash(f"Created group {name}.")
    except Exception as exc:
        flash(f"Failed to create group: {exc}")
    return redirect(url_for("admin.index"))

@bp.route("/groups/members/add/", methods=["POST"])
@admin_required
def add_group_member():
    user_id = request.form.get("user_id", "").strip()
    group_id_raw = request.form.get("group_id", "").strip()

    try:
        group_id = int(group_id_raw)
    except ValueError:
        flash("Group is required.")
        return redirect(url_for("admin.index"))

    if not user_id:
        flash("User is required.")
        return redirect(url_for("admin.index"))

    try:
        db.add_user_to_group(user_id=user_id, group_id=group_id)
        flash("Added user to group.")
    except Exception as exc:
        flash(f"Failed to add user to group: {exc}")
    return redirect(url_for("admin.index"))

@bp.route("/groups/members/remove/", methods=["POST"])
@admin_required
def remove_group_member():
    user_id = request.form.get("user_id", "").strip()
    group_id_raw = request.form.get("group_id", "").strip()

    try:
        group_id = int(group_id_raw)
    except ValueError:
        flash("Group is required.")
        return redirect(url_for("admin.index"))

    if not user_id:
        flash("User is required.")
        return redirect(url_for("admin.index"))

    try:
        db.remove_user_from_group(user_id=user_id, group_id=group_id)
        flash("Removed user from group.")
    except Exception as exc:
        flash(f"Failed to remove user from group: {exc}")
    return redirect(url_for("admin.index"))
