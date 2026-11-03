from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .config import get_settings
from .database import SessionLocal, init_db

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
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Red Thread — From fragmented digital traces to an explainable, human-reviewed "
            "investigation picture. Local-first evidence preservation, parsing, correlation "
            "and human-reviewed findings."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def no_store_api_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

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
