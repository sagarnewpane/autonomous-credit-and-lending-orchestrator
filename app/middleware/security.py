"""
Security middleware: headers, rate limiting, request logging, audit logging.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security")
audit_logger = logging.getLogger("audit")


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, app, login_limit: int = 5, api_limit: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.login_limit = login_limit
        self.api_limit = api_limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, key: str, limit: int) -> bool:
        now = time.time()
        cutoff = now - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= limit:
            return True
        self._hits[key].append(now)
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = self._client_ip(request)
        path = request.url.path

        # Stricter limit on auth endpoints
        if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/signup"):
            key = f"auth:{ip}"
            if self._is_rate_limited(key, self.login_limit):
                logger.warning(f"Rate limit exceeded for auth from {ip}")
                return Response(
                    content='{"detail":"Too many requests. Please try again later."}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self.window), "Content-Type": "application/json"},
                )

        # General API rate limit
        if path.startswith("/api/"):
            key = f"api:{ip}"
            if self._is_rate_limited(key, self.api_limit):
                logger.warning(f"Rate limit exceeded for API from {ip}")
                return Response(
                    content='{"detail":"Too many requests. Please try again later."}',
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self.window), "Content-Type": "application/json"},
                )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Request Logging
# ---------------------------------------------------------------------------
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with timing and status."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")

        response = await call_next(request)

        duration_ms = round((time.time() - start) * 1000, 1)
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration_ms}ms "
            f"ip={ip}"
        )
        return response


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------
def log_auth_event(event_type: str, email: str, ip: str, success: bool, detail: str = ""):
    """Log authentication events: login, signup, logout, refresh."""
    status_str = "SUCCESS" if success else "FAILURE"
    audit_logger.info(
        f"[AUTH] {event_type} | {status_str} | email={email} | ip={ip} | {detail}"
    )


def log_admin_action(admin_id: int, action: str, target: str, detail: str = ""):
    """Log admin actions: update loan, update user, bulk update."""
    audit_logger.info(
        f"[ADMIN] {action} | admin_id={admin_id} | target={target} | {detail}"
    )


def log_security_event(event_type: str, ip: str, detail: str = ""):
    """Log security events: rate limit, unauthorized access, etc."""
    audit_logger.warning(
        f"[SECURITY] {event_type} | ip={ip} | {detail}"
    )
