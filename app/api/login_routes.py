from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_dependencies.dependencies import get_current_user
from app.models.user import RefreshRequest, TokenResponse, UserCreate, UserRead
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.services.user_service import create_user, get_user_by_email

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_read(user: dict) -> UserRead:
    return UserRead(
        id=user["id"],
        email=user["email"],
        is_active=user.get("is_active", True),
        is_admin=user.get("is_admin", False),
        created_at=user.get("created_at"),
    )


def _token_response(user: dict) -> TokenResponse:
    from app.services.auth_service import ACCESS_TOKEN_EXPIRE_MINUTES

    access_token = create_access_token(user["id"], user["email"], user.get("is_admin", False))
    refresh_token = create_refresh_token(user["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_read(user),
    )


@auth_router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(user_create: UserCreate) -> TokenResponse:
    existing = get_user_by_email(user_create.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = create_user(user_create.email, hash_password(user_create.password))
    return _token_response(user)


@auth_router.post("/login", response_model=TokenResponse)
async def login(user_create: UserCreate) -> TokenResponse:
    user = get_user_by_email(user_create.email)
    if not user or not verify_password(user_create.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return _token_response(user)


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(refresh.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    from app.services.user_service import get_user_by_id

    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return _token_response(user)


@auth_router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: dict = Depends(get_current_user),
) -> UserRead:
    return _user_read(current_user)


@auth_router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    return {"message": "Logged out successfully"}
