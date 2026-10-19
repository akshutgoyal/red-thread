from __future__ import annotations

import importlib.util
import shutil

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..schemas.common import HealthResponse

router = APIRouter(tags=["health"])


def selected_provider(settings: Settings) -> str:
    provider = (settings.ai_provider or "auto").strip().lower()
    if provider == "auto":
        if settings.commandcode_api_key:
            return "commandcode"
        if settings.tokenharbor_api_key:
            return "tokenharbor"
        return "none"
    return provider


def provider_configured(settings: Settings, provider: str) -> bool:
    if provider == "commandcode":
        return bool(settings.commandcode_api_key)
    if provider == "tokenharbor":
        return bool(settings.tokenharbor_api_key)
    return False


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health must report a degraded database
        database = "error"

    provider = selected_provider(settings)
    ocr_available = (
        importlib.util.find_spec("pytesseract") is not None
        and shutil.which(settings.tesseract_cmd or "tesseract") is not None
    )
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        database=database,
        ai_provider=provider,
        ai_configured=provider_configured(settings, provider),
        ocr_available=ocr_available,
    )
