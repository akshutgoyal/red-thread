from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_case_or_404, require_case_id
from ..schemas.relationship import (
    AnnotationCreate,
    AnnotationRead,
    RelationshipDetail,
    RelationshipListResponse,
    RelationshipRead,
    RelationshipReviewRequest,
    ReviewDecisionRead,
)
from ..services import relationship_service

router = APIRouter(tags=["relationships"])


def _detail(db: Session, relationship_id: str, case_id: str) -> RelationshipDetail:
    relationship = relationship_service.get_relationship(db, relationship_id, case_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found in this case.")
    detail = RelationshipDetail.model_validate(relationship)
    detail.reviews = [
        ReviewDecisionRead.model_validate(item)
        for item in relationship_service.list_reviews(db, case_id, "relationship", relationship.id)
    ]
    return detail


@router.get(
    "/cases/{case_id}/relationships",
    response_model=RelationshipListResponse,
)
def list_relationships(
    case_id: str,
    relationship_type: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> RelationshipListResponse:
    get_case_or_404(db, case_id)
    items, total = relationship_service.list_relationships(
        db,
        case_id,
        relationship_type=relationship_type,
        classification=classification,
        review_status=review_status,
        confidence=confidence,
        limit=limit,
        offset=offset,
    )
    return RelationshipListResponse(
        items=[RelationshipRead.model_validate(item) for item in items],
        total=total,
    )


@router.get("/relationships/{relationship_id}", response_model=RelationshipDetail)
def get_relationship(
    relationship_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> RelationshipDetail:
    return _detail(db, relationship_id, case_id)


@router.post(
    "/relationships/{relationship_id}/review",
    response_model=RelationshipDetail,
)
def review_relationship(
    relationship_id: str,
    payload: RelationshipReviewRequest,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> RelationshipDetail:
    try:
        relationship = relationship_service.review_relationship(
            db,
            relationship_id,
            case_id,
            decision=payload.decision,
            reviewer=payload.reviewer,
            note=payload.note,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found in this case.")
    return _detail(db, relationship_id, case_id)


@router.get(
    "/cases/{case_id}/annotations",
    response_model=list[AnnotationRead],
)
def list_annotations(
    case_id: str,
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AnnotationRead]:
    get_case_or_404(db, case_id)
    return [
        AnnotationRead.model_validate(item)
        for item in relationship_service.list_annotations(
            db, case_id, target_type=target_type, target_id=target_id
        )
    ]


@router.post(
    "/cases/{case_id}/annotations",
    response_model=AnnotationRead,
    status_code=201,
)
def create_annotation(
    case_id: str,
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
) -> AnnotationRead:
    get_case_or_404(db, case_id)
    try:
        annotation = relationship_service.create_annotation(db, case_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return AnnotationRead.model_validate(annotation)
