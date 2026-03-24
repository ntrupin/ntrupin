from datetime import datetime
import os

from flask import g, has_request_context, session

SESSION_ACCESS_TOKEN_KEY = "sb_access_token"

def _supabase_url() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise ValueError("Expected SUPABASE_URL")
    return url

def _supabase_anon_key() -> str:
    key = os.getenv("SUPABASE_ANON_KEY")
    if not key:
        raise ValueError("Expected SUPABASE_ANON_KEY")
    return key

def _supabase_service_key() -> str:
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not key:
        raise ValueError("Expected SUPABASE_SERVICE_KEY")
    return key

def get():
    if "db" not in g:
        import supabase

        g.db = supabase.create_client(_supabase_url(), _supabase_anon_key())
        if has_request_context():
            access_token = session.get(SESSION_ACCESS_TOKEN_KEY)
            if access_token:
                g.db.postgrest.auth(access_token)
    return g.db

def get_service():
    if "service_db" not in g:
        import supabase

        g.service_db = supabase.create_client(_supabase_url(), _supabase_service_key())
    return g.service_db

def _parse_admin_emails() -> set[str]:
    raw = os.getenv("SUPABASE_ADMIN_EMAILS", "")
    emails = [email.strip().lower() for email in raw.split(",")]
    return {email for email in emails if email}

def is_bootstrap_admin_email(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in _parse_admin_emails()

def upsert_user_role(user_id: str, role: str) -> None:
    database = get_service()
    (
        database.table("app_roles")
        .upsert(
            {
                "user_id": user_id,
                "role": role,
            },
            on_conflict="user_id",
        )
        .execute()
    )

def bootstrap_admin_role(user_id: str, email: str | None) -> None:
    if not is_bootstrap_admin_email(email):
        return
    upsert_user_role(user_id, "admin")

def get_user_role(user_id: str) -> str | None:
    database = get()
    data = (
        database.table("app_roles")
        .select("role")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data
    return data[0]["role"] if data else None

def list_roles() -> list[dict]:
    database = get()
    return (
        database.table("app_roles")
        .select("user_id,role")
        .order("created_at", desc=False)
        .execute()
    ).data

def list_groups() -> list[dict]:
    database = get()
    return (
        database.table("groups")
        .select("id,name,slug,created_at")
        .order("name")
        .execute()
    ).data

def list_groups_by_ids(group_ids: list[int]) -> list[dict]:
    normalized = sorted({int(group_id) for group_id in group_ids})
    if not normalized:
        return []
    database = get()
    return (
        database.table("groups")
        .select("id,name,slug,created_at")
        .in_("id", normalized)
        .order("name")
        .execute()
    ).data

def create_group(name: str, slug: str, created_by: str) -> dict:
    database = get_service()
    response = (
        database.table("groups")
        .insert(
            {
                "name": name,
                "slug": slug,
                "created_by": created_by,
            }
        )
        .execute()
    ).data
    return response[0]

def get_group_by_slug(slug: str) -> dict | None:
    database = get_service()
    rows = (
        database.table("groups")
        .select("id,name,slug,created_at")
        .eq("slug", slug)
        .limit(1)
        .execute()
    ).data
    return rows[0] if rows else None

def ensure_default_role_group(user_id: str, is_admin: bool) -> dict | None:
    admin_group = get_group_by_slug("admin")
    if not admin_group:
        admin_group = create_group("Admin", "admin", user_id)

    members_group = get_group_by_slug("members")
    if not members_group:
        members_group = create_group("Members", "members", user_id)

    group = admin_group if is_admin else members_group
    if not group:
        return None
    add_user_to_group(user_id=user_id, group_id=group["id"])
    return group

def sync_default_role_group(user_id: str, role: str, created_by: str | None = None) -> dict | None:
    creator_id = created_by or user_id
    admin_group = get_group_by_slug("admin")
    if not admin_group:
        admin_group = create_group("Admin", "admin", creator_id)

    members_group = get_group_by_slug("members")
    if not members_group:
        members_group = create_group("Members", "members", creator_id)

    is_admin = role == "admin"
    target_group = admin_group if is_admin else members_group
    other_group = members_group if is_admin else admin_group
    if not target_group:
        return None

    add_user_to_group(user_id=user_id, group_id=target_group["id"])
    if other_group:
        remove_user_from_group(user_id=user_id, group_id=other_group["id"])
    return target_group

def get_user_group_ids(user_id: str) -> list[int]:
    database = get()
    rows = (
        database.table("group_memberships")
        .select("group_id")
        .eq("user_id", user_id)
        .execute()
    ).data
    return sorted({row["group_id"] for row in rows})

def list_group_memberships() -> list[dict]:
    database = get()
    return (
        database.table("group_memberships")
        .select("group_id,user_id,created_at")
        .order("group_id")
        .execute()
    ).data

def add_user_to_group(user_id: str, group_id: int) -> None:
    database = get_service()
    (
        database.table("group_memberships")
        .upsert(
            {
                "group_id": group_id,
                "user_id": user_id,
            },
            on_conflict="group_id,user_id",
        )
        .execute()
    )

def remove_user_from_group(user_id: str, group_id: int) -> None:
    database = get_service()
    (
        database.table("group_memberships")
        .delete()
        .eq("group_id", group_id)
        .eq("user_id", user_id)
        .execute()
    )

def _replace_linked_groups(table_name: str, content_field: str, content_id: int, group_ids: list[int]) -> None:
    database = get()
    (
        database.table(table_name)
        .delete()
        .eq(content_field, content_id)
        .execute()
    )
    normalized = sorted({int(group_id) for group_id in group_ids})
    if not normalized:
        return
    rows = [
        {
            content_field: content_id,
            "group_id": group_id,
        }
        for group_id in normalized
    ]
    database.table(table_name).insert(rows).execute()

def replace_writing_groups(writing_id: int, group_ids: list[int]) -> None:
    _replace_linked_groups("writing_groups", "writing_id", writing_id, group_ids)

def replace_project_groups(project_id: int, group_ids: list[int]) -> None:
    _replace_linked_groups("project_groups", "project_id", project_id, group_ids)

def _get_linked_group_ids(table_name: str, content_field: str, content_id: int) -> list[int]:
    database = get()
    rows = (
        database.table(table_name)
        .select("group_id")
        .eq(content_field, content_id)
        .execute()
    ).data
    return sorted({row["group_id"] for row in rows})

def get_writing_group_ids(writing_id: int) -> list[int]:
    return _get_linked_group_ids("writing_groups", "writing_id", writing_id)

def get_project_group_ids(project_id: int) -> list[int]:
    return _get_linked_group_ids("project_groups", "project_id", project_id)

def _get_content_ids_for_groups(table_name: str, content_field: str, group_ids: list[int]) -> list[int]:
    normalized = sorted({int(group_id) for group_id in group_ids})
    if not normalized:
        return []
    database = get()
    rows = (
        database.table(table_name)
        .select(content_field)
        .in_("group_id", normalized)
        .execute()
    ).data
    return sorted({int(row[content_field]) for row in rows})

def get_writing_ids_for_group_ids(group_ids: list[int]) -> list[int]:
    return _get_content_ids_for_groups("writing_groups", "writing_id", group_ids)

def get_project_ids_for_group_ids(group_ids: list[int]) -> list[int]:
    return _get_content_ids_for_groups("project_groups", "project_id", group_ids)

def _get_group_map(table_name: str, content_field: str, content_ids: list[int]) -> dict[int, list[str]]:
    normalized_ids = sorted({int(content_id) for content_id in content_ids})
    if not normalized_ids:
        return {}
    database = get()
    memberships = (
        database.table(table_name)
        .select(f"{content_field},group_id")
        .in_(content_field, normalized_ids)
        .execute()
    ).data
    group_ids = sorted({row["group_id"] for row in memberships})
    if not group_ids:
        return {}
    groups = (
        database.table("groups")
        .select("id,name")
        .in_("id", group_ids)
        .execute()
    ).data
    names_by_id = {group["id"]: group["name"] for group in groups}
    grouped: dict[int, list[str]] = {content_id: [] for content_id in normalized_ids}
    for membership in memberships:
        content_id = int(membership[content_field])
        group_name = names_by_id.get(membership["group_id"])
        if not group_name:
            continue
        grouped.setdefault(content_id, []).append(group_name)
    for content_id, names in grouped.items():
        grouped[content_id] = sorted(set(names))
    return grouped

def get_writing_group_map(writing_ids: list[int]) -> dict[int, list[str]]:
    return _get_group_map("writing_groups", "writing_id", writing_ids)

def get_project_group_map(project_ids: list[int]) -> dict[int, list[str]]:
    return _get_group_map("project_groups", "project_id", project_ids)

def list_auth_users(page: int = 1, per_page: int = 1000):
    database = get_service()
    return database.auth.admin.list_users(page=page, per_page=per_page)

def create_auth_user(email: str, password: str):
    database = get_service()
    return database.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
        }
    ).user

def get_updates(n: int | None = None) -> list[dict]:
    database = get()
    updates = (
        database.table("updates")
        .select("*")
        .order("date", desc=True)
    )
    if n:
        updates = updates.limit(n)
    updates = updates.execute().data
    for update in updates:
        update["date"] = datetime.fromisoformat(update["date"])
    return updates
