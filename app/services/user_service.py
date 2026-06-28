from __future__ import annotations

from typing import Any

from app.db.supabase import supabase

TABLE = "users"


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    result = supabase.table(TABLE).select("*").eq("id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    result = supabase.table(TABLE).select("*").eq("email", email).limit(1).execute()
    return result.data[0] if result.data else None


def create_user(email: str, hashed_password: str) -> dict[str, Any]:
    result = (
        supabase.table(TABLE)
        .insert({"email": email, "hashed_password": hashed_password})
        .execute()
    )
    return result.data[0]
