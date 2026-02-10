from datetime import datetime
import os

from flask import g
import supabase

def get():
    if "db" not in g:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Expected SUPABASE_URL and SUPABASE_KEY")
        g.db = supabase.create_client(url, key)
    return g.db

def get_user(username: str) -> dict | None:
    database = get()
    user = (
        database.table("users")
        .select("id,username,password")
        .eq("username", username)
        .execute()
    ).data
    return user[0] if user else None

def insert_user(username: str, password: str) -> None:
    database = get()
    database.table("users").insert({
        "username": username,
        "password": password
    }).execute()

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
