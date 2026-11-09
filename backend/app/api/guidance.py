from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..database import get_db
from ..dependencies import get_case_or_404
from ..schemas.guidance import (
    EventReviewListResponse,
    EventReviewRead,
    EventReviewRequest,
    GuidanceResponse,
    NarrativeResponse,
)
from ..services import guidance_service, narrative_service

router = APIRouter(tags=["guidance"])


@router.get("/cases/{case_id}/guidance", response_model=GuidanceResponse)
def get_guidance(
    case_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GuidanceResponse:
    get_case_or_404(db, case_id)
    try:
        return guidance_service.build_guidance(db, case_id, settings)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/cases/{case_id}/narrative", response_model=NarrativeResponse)
def get_narrative(
    case_id: str,
    db: Session = Depends(get_db),
) -> NarrativeResponse:
    get_case_or_404(db, case_id)
    return narrative_service.build_narrative(db, case_id)


@router.post(
    "/cases/{case_id}/events/{event_id}/review",
    response_model=EventReviewRead,
)
def review_event(
    case_id: str,
    event_id: str,
    payload: EventReviewRequest,
    db: Session = Depends(get_db),
) -> EventReviewRead:
    get_case_or_404(db, case_id)
    try:
        return narrative_service.review_event(db, case_id, event_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(
    "/cases/{case_id}/event-reviews",
    response_model=EventReviewListResponse,
)
def list_event_reviews(
    case_id: str,
    db: Session = Depends(get_db),
) -> EventReviewListResponse:
    get_case_or_404(db, case_id)
    return narrative_service.list_event_reviews(db, case_id)
