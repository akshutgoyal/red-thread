from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..dependencies import get_case_or_404
from ..schemas.ai import (
    AiAnswerResponse,
    AiAskRequest,
    AiStatusResponse,
    AiSuggestionsResponse,
)
from ..services import ai_service, suggestion_service

router = APIRouter(tags=["ai"])


@router.get("/ai/status", response_model=AiStatusResponse)
async def ai_status(
    check: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
) -> AiStatusResponse:
    return AiStatusResponse(**await ai_service.get_status(settings, check=check))


@router.get(
    "/cases/{case_id}/ai/suggestions",
    response_model=AiSuggestionsResponse,
)
def ai_suggestions(
    case_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AiSuggestionsResponse:
    get_case_or_404(db, case_id)
    return suggestion_service.build_suggestions(db, case_id, settings)


@router.post("/cases/{case_id}/ai/ask", response_model=AiAnswerResponse)
async def ask_ai(
    case_id: str,
    payload: AiAskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AiAnswerResponse:
    get_case_or_404(db, case_id)
    try:
        result = await ai_service.ask_ai(
            db,
            case_id,
            payload.question,
            settings,
            focus_type=payload.focus_type,
            focus_id=payload.focus_id,
        )
    except ai_service.AIError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    return AiAnswerResponse(**result)
