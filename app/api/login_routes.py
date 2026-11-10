from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth_dependencies.dependencies import get_current_user
from app.middleware.security import log_admin_action, log_auth_event
from app.models.user import RefreshRequest, TokenResponse, UserCreate, UserRead
from app.services.auth_service import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.services.user_service import create_user, get_user_by_email

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_read(user: dict) -> UserRead:
    return UserRead(
        id=user["id"],
        email=user["email"],
        applicant_id=user.get("applicant_id"),
        is_active=user.get("is_active", True),
        is_admin=user.get("is_admin", False),
        created_at=user.get("created_at"),
    )


def _token_response(user: dict) -> TokenResponse:
    from app.services.auth_service import ACCESS_TOKEN_EXPIRE_MINUTES

    access_token = create_access_token(
        user["id"],
        user["email"],
        user.get("is_admin", False),
        user.get("applicant_id"),
    )
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
def signup(user_create: UserCreate, request: Request) -> TokenResponse:
    ip = _get_client_ip(request)

    # Validate password strength
    pw_errors = validate_password_strength(user_create.password)
    if pw_errors:
        log_auth_event("SIGNUP", user_create.email, ip, False, "weak password")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(pw_errors),
        )

    existing = get_user_by_email(user_create.email)
    if existing:
        log_auth_event("SIGNUP", user_create.email, ip, False, "email already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = create_user(user_create.email, hash_password(user_create.password))
    log_auth_event("SIGNUP", user_create.email, ip, True)
    return _token_response(user)


@auth_router.post("/login", response_model=TokenResponse)
def login(user_create: UserCreate, request: Request) -> TokenResponse:
    ip = _get_client_ip(request)
    user = get_user_by_email(user_create.email)

    if not user or not verify_password(user_create.password, user["hashed_password"]):
        log_auth_event("LOGIN", user_create.email, ip, False, "invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        log_auth_event("LOGIN", user_create.email, ip, False, "account deactivated")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    log_auth_event("LOGIN", user_create.email, ip, True)
    return _token_response(user)


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh: RefreshRequest, request: Request) -> TokenResponse:
    ip = _get_client_ip(request)
    try:
        payload = decode_token(refresh.refresh_token)
    except Exception:
        log_auth_event("REFRESH", "unknown", ip, False, "invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        log_auth_event("REFRESH", "unknown", ip, False, "wrong token type")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    from app.services.user_service import get_user_by_id

    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", True):
        log_auth_event("REFRESH", "unknown", ip, False, "user not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    log_auth_event("REFRESH", user.get("email", ""), ip, True)
    return _token_response(user)


@auth_router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: dict = Depends(get_current_user),
) -> UserRead:
    return _user_read(current_user)


@auth_router.post("/logout")
def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    ip = _get_client_ip(request)
    # Blacklist the current access token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                blacklist_token(jti)
        except Exception:
            pass

    log_auth_event("LOGOUT", current_user.get("email", ""), ip, True)
    return {"message": "Logged out successfully"}
