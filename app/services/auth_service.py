from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-to-a-real-256-bit-secret-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ── Token Blacklist (in-memory; swap for Redis in production) ──────────────
_token_blacklist: set[str] = set()


def blacklist_token(jti: str) -> None:
    """Add a token's jti to the blacklist."""
    _token_blacklist.add(jti)


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token has been revoked."""
    return jti in _token_blacklist


# ── Password Hashing ──────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── Password Strength Validation ──────────────────────────────────────────
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128


def validate_password_strength(password: str) -> list[str]:
    """
    Validate password meets security requirements.
    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    if len(password) < _PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {_PASSWORD_MIN_LENGTH} characters long")
    if len(password) > _PASSWORD_MAX_LENGTH:
        errors.append(f"Password must be at most {_PASSWORD_MAX_LENGTH} characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character")
    return errors


# ── JWT Token Operations ──────────────────────────────────────────────────
def create_access_token(
    user_id: int,
    email: str,
    is_admin: bool = False,
    applicant_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "applicant_id": applicant_id,
        "type": "access",
        "jti": os.urandom(16).hex(),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": os.urandom(16).hex(),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    # Check blacklist
    jti = payload.get("jti")
    if jti and is_token_blacklisted(jti):
        raise jwt.InvalidTokenError("Token has been revoked")
    return payload
