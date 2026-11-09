from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.router import api_router
from .config import get_settings
from .database import SessionLocal, init_db
from .services.auth_service import authorize_request
from .rate_limit import rate_limit_request

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    if settings.seed_demo:
        from .services.demo_seed_service import seed_demo_if_needed

        db = SessionLocal()
        try:
            result = seed_demo_if_needed(db, settings)
            logger.info("Demo seed result: %s", result)
        except Exception:  # noqa: BLE001 - startup must not crash on seed failure
            logger.exception("Demo seed failed; starting without seeded data.")
        finally:
            db.close()
    try:
        from .services.demo_cleanup_service import cleanup_expired_demo_copies

        db = SessionLocal()
        try:
            removed = cleanup_expired_demo_copies(db)
            logger.info("Demo copy cleanup removed %s cases.", removed)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - cleanup must not block startup
        logger.exception("Demo copy cleanup failed.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    docs_enabled = settings.docs_enabled
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        description=(
            "Red Thread — From fragmented digital traces to an explainable, human-reviewed "
            "investigation picture. Local-first evidence preservation, parsing, correlation "
            "and human-reviewed findings."
        ),
        lifespan=lifespan,
        dependencies=[Depends(authorize_request), Depends(rate_limit_request)],
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cross-Origin-Resource-Policy"] = "same-site"
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), payment=()"
            )
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
            if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
        return response

    @application.middleware("http")
    async def csrf_origin_guard(request, call_next):
        """Reject state-changing cross-site requests.

        Sessions travel in a SameSite=None cookie so the Vercel frontend can
        talk to the Render API. SameSite therefore provides no CSRF protection,
        and the Origin header becomes the control that stops a third-party site
        from issuing authenticated writes.
        """
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        origin = (request.headers.get("origin") or "").strip().rstrip("/")
        if not origin:
            # Non-browser clients (curl, tests) send no Origin header. They also
            # cannot be tricked into sending a victim's cookie, so this is safe.
            return await call_next(request)
        allowed = {value.rstrip("/") for value in settings.cors_origin_list}
        if origin not in allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site request blocked."},
            )
        return await call_next(request)

    # A shipped or short secret would let anyone forge a session. In production
    # it is replaced with a random per-process value: sessions are invalidated
    # on restart, but forged tokens remain impossible.
    if settings.environment.strip().lower() == "production" and settings.session_secret_is_insecure:
        import secrets

        settings.session_secret = secrets.token_hex(32)
        logger.critical(
            "RED_THREAD_SESSION_SECRET is missing or too short. Using an ephemeral "
            "secret for this process: all sessions reset on restart. Set "
            "RED_THREAD_SESSION_SECRET (openssl rand -hex 32) to keep users signed in."
        )

    application.include_router(api_router, prefix="/api")

    @application.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/health",
            "mode": "local-first",
        }

    return application


app = create_app()
