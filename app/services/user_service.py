from __future__ import annotations

import uuid
from typing import Any

from app.db import db

TABLE = "users"


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    result = db.table(TABLE).select("*").eq("id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    result = db.table(TABLE).select("*").eq("email", email).limit(1).execute()
    return result.data[0] if result.data else None


def create_user(email: str, hashed_password: str) -> dict[str, Any]:
    applicant_id = f"AP-{uuid.uuid4().hex[:8].upper()}"
    result = db.table(TABLE).insert({
        "email": email,
        "hashed_password": hashed_password,
        "applicant_id": applicant_id,
    })
    return result.data[0]
