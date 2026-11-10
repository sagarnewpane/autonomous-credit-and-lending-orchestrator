import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin_routes import admin_router
from app.api.login_routes import auth_router
from app.api.routes import router as api_router
from app.middleware.security import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)

# ── Logging Configuration ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("app")

app = FastAPI(
    title="Autonomous Credit & Lending Orchestrator",
    docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc",
)

DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
]


def _cors_origins() -> list[str]:
    """Origins allowed by CORS. Override with CORS_ORIGINS (comma-separated, or *)."""
    configured = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    return configured or DEV_CORS_ORIGINS


_cors_origins_value = _cors_origins()
_cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX") or None

# ── Security Middleware (order matters: last added = first executed) ──────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, login_limit=5, api_limit=60, window_seconds=60)
app.add_middleware(RequestLoggingMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_value,
    allow_origin_regex=_cors_origin_regex,
    # A wildcard origin and credentials cannot be combined. The app authenticates with a
    # bearer token, not cookies, so credentials are not needed for the demo deployment.
    allow_credentials="*" not in _cors_origins_value,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Global Exception Handler ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ── Routes ───────────────────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(admin_router)
