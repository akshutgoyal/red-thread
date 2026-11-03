from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_case_or_404
from ..schemas.analysis import (
    EntityDetailResponse,
    ReconstructionResponse,
    SpatialResponse,
)
from ..services import analysis_service

router = APIRouter(tags=["analysis"])


@router.get(
    "/cases/{case_id}/entities/{entity_id}",
    response_model=EntityDetailResponse,
)
def get_entity_detail(
    case_id: str,
    entity_id: str,
    db: Session = Depends(get_db),
) -> EntityDetailResponse:
    get_case_or_404(db, case_id)
    detail = analysis_service.entity_detail(db, case_id, entity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found in this case.")
    return detail


@router.get("/cases/{case_id}/spatial", response_model=SpatialResponse)
def get_spatial(
    case_id: str,
    entity_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SpatialResponse:
    get_case_or_404(db, case_id)
    return analysis_service.spatial(db, case_id, entity_id=entity_id)


@router.get("/cases/{case_id}/reconstruction", response_model=ReconstructionResponse)
def get_reconstruction(
    case_id: str,
    db: Session = Depends(get_db),
) -> ReconstructionResponse:
    get_case_or_404(db, case_id)
    try:
        return analysis_service.reconstruction(db, case_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
