from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..dependencies import (
    get_case_or_404,
    get_evidence_or_404,
    require_case_id,
)
from ..models import AuditEvent, Entity, Event, EventEntity, Evidence, Finding, FindingEvidence
from ..schemas.common import AuditEventRead
from ..schemas.event import (
    EntityRead,
    EventListResponse,
    EventRead,
    GraphResponse,
    TimelineResponse,
)
from ..schemas.evidence import EvidenceRead, HashVerifyResponse, ParseResponse
from ..schemas.finding import FindingListResponse, FindingRead, FindingReviewRequest
from ..services import (
    audit_service,
    correlation_service,
    evidence_service,
    investigation_service,
    reconciliation_service,
    storage_service,
)

router = APIRouter(tags=["evidence"])

EVENT_EXPORT_FIELDS = [
    "event_id",
    "event_type",
    "timestamp_raw",
    "timestamp_normalized",
    "timestamp_confidence",
    "source_filename",
    "source_locator",
    "source_ip",
    "username",
    "auth_status",
    "auth_method",
    "pid",
    "port",
    "invalid_user",
    "session_event",
    "target_user",
    "command",
]

FINDING_EXPORT_FIELDS = [
    "finding_id",
    "severity",
    "title",
    "status",
    "detection_method",
    "confidence",
    "explanation",
    "limitations",
    "alternative_explanations",
    "evidence_links",
]


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail=f"Invalid {field} timestamp: {value!r}"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_filters(
    case_id: str,
    event_type: str | None,
    evidence_id: str | None,
    entity: str | None,
    confidence: str | None,
    start: str | None,
    end: str | None,
) -> list:
    filters = [Event.case_id == case_id]
    if event_type:
        filters.append(Event.event_type == event_type)
    if evidence_id:
        filters.append(Event.evidence_id == evidence_id)
    if confidence:
        filters.append(Event.timestamp_confidence == confidence)
    if start:
        filters.append(Event.timestamp_normalized >= _parse_datetime(start, "start"))
    if end:
        filters.append(Event.timestamp_normalized <= _parse_datetime(end, "end"))
    if entity:
        subquery = (
            select(EventEntity.event_id)
            .join(Entity, Entity.id == EventEntity.entity_id)
            .where(
                (Entity.value_normalized == entity)
                | (Entity.value_original == entity)
            )
        )
        filters.append(Event.id.in_(subquery))
    return filters


@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceRead,
    status_code=201,
)
def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EvidenceRead:
    case = get_case_or_404(db, case_id)
    return evidence_service.create_evidence(db, case, file)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceRead])
def list_evidence(case_id: str, db: Session = Depends(get_db)) -> list[EvidenceRead]:
    get_case_or_404(db, case_id)
    return evidence_service.list_evidence(db, case_id)


@router.get("/evidence/{evidence_id}", response_model=EvidenceRead)
def get_evidence(
    evidence_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> EvidenceRead:
    return get_evidence_or_404(db, evidence_id, case_id)


@router.post("/evidence/{evidence_id}/verify", response_model=HashVerifyResponse)
def verify_evidence(
    evidence_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> HashVerifyResponse:
    evidence = get_evidence_or_404(db, evidence_id, case_id)
    return HashVerifyResponse(**evidence_service.verify_evidence(db, evidence))


@router.post("/evidence/{evidence_id}/parse", response_model=ParseResponse)
def parse_evidence(
    evidence_id: str,
    parser: str | None = Query(default=None),
    reparse: bool = Query(default=False),
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> ParseResponse:
    evidence = get_evidence_or_404(db, evidence_id, case_id)
    return ParseResponse(
        **investigation_service.parse_evidence(
            db,
            evidence,
            parser_hint=parser,
            reparse=reparse,
        )
    )


@router.get("/evidence/{evidence_id}/content")
def evidence_content(
    evidence_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
):
    evidence = get_evidence_or_404(db, evidence_id, case_id)
    try:
        stream = storage_service.iter_object(evidence.relative_path)
    except storage_service.StorageObjectNotFound as error:
        raise HTTPException(
            status_code=404, detail="Evidence file is missing from the vault."
        ) from error
    except storage_service.StorageError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return StreamingResponse(
        stream,
        media_type=evidence.media_type,
        headers={"Content-Disposition": evidence_service.content_disposition(evidence)},
    )


@router.get("/evidence/{evidence_id}/text")
def evidence_text(
    evidence_id: str,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> dict:
    evidence = get_evidence_or_404(db, evidence_id, case_id)
    return evidence_service.read_text_preview(evidence)


@router.get("/cases/{case_id}/events", response_model=EventListResponse)
def list_events(
    case_id: str,
    event_type: str | None = Query(default=None),
    evidence_id: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    timestamp_confidence: str | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> EventListResponse:
    get_case_or_404(db, case_id)
    filters = _event_filters(
        case_id, event_type, evidence_id, entity, timestamp_confidence, start, end
    )
    query = select(Event).where(*filters)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            query.order_by(
                Event.timestamp_normalized.is_(None),
                Event.timestamp_normalized.asc(),
                Event.created_at.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return EventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/cases/{case_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    case_id: str,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    get_case_or_404(db, case_id)
    items = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id, Event.timestamp_normalized.is_not(None))
            .order_by(Event.timestamp_normalized.asc())
            .limit(limit)
        )
    )
    undated = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id, Event.timestamp_normalized.is_(None))
            .order_by(Event.created_at.asc())
            .limit(limit)
        )
    )
    return TimelineResponse(items=items, undated=undated, total=len(items) + len(undated))


@router.get("/cases/{case_id}/entities", response_model=list[EntityRead])
def list_entities(
    case_id: str,
    entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[EntityRead]:
    get_case_or_404(db, case_id)
    query = select(Entity).where(Entity.case_id == case_id)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    return list(db.scalars(query.order_by(Entity.entity_type, Entity.value_original)))


@router.get("/cases/{case_id}/graph", response_model=GraphResponse)
def get_graph(
    case_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    include_temporal: bool = Query(default=False),
    temporal_window_seconds: int = Query(default=300, ge=1, le=86400),
    db: Session = Depends(get_db),
) -> GraphResponse:
    get_case_or_404(db, case_id)
    return correlation_service.build_graph(
        db,
        case_id,
        limit=limit,
        include_temporal=include_temporal,
        temporal_window_seconds=temporal_window_seconds,
    )


@router.post("/cases/{case_id}/reconcile")
def reconcile_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    get_case_or_404(db, case_id)
    findings = reconciliation_service.run(db, case_id)
    db.commit()
    return {
        "case_id": case_id,
        "findings_created": len(findings),
        "findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "title": finding.title,
                "status": finding.status,
            }
            for finding in findings
        ],
    }


@router.get("/cases/{case_id}/findings", response_model=FindingListResponse)
def list_findings(
    case_id: str,
    severity: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FindingListResponse:
    get_case_or_404(db, case_id)
    filters = [Finding.case_id == case_id]
    if severity:
        filters.append(Finding.severity == severity)
    if status_value:
        filters.append(Finding.status == status_value)
    if category:
        filters.append(Finding.category == category)
    query = (
        select(Finding)
        .where(*filters)
        .options(selectinload(Finding.evidence_links))
        .order_by(Finding.created_at.desc())
    )
    total = db.scalar(
        select(func.count()).select_from(select(Finding).where(*filters).subquery())
    ) or 0
    return FindingListResponse(items=list(db.scalars(query)), total=total)


@router.post("/findings/{finding_id}/review", response_model=FindingRead)
def review_finding(
    finding_id: str,
    payload: FindingReviewRequest,
    case_id: str = Depends(require_case_id),
    db: Session = Depends(get_db),
) -> FindingRead:
    finding = db.get(Finding, finding_id)
    if finding is None or finding.case_id != case_id:
        raise HTTPException(status_code=404, detail="Finding not found in this case.")
    finding.status = payload.status
    finding.reviewer_note = payload.reviewer_note
    finding.reviewed_at = datetime.now(timezone.utc)
    audit_service.record(
        db,
        case_id,
        "finding.reviewed",
        details={
            "finding_id": finding.id,
            "status": payload.status,
            "reviewer_note": payload.reviewer_note,
        },
    )
    db.commit()
    result = db.scalar(
        select(Finding)
        .where(Finding.id == finding_id)
        .options(selectinload(Finding.evidence_links))
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    return result


@router.get("/cases/{case_id}/audit", response_model=list[AuditEventRead])
def list_audit(case_id: str, db: Session = Depends(get_db)) -> list[AuditEventRead]:
    get_case_or_404(db, case_id)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.created_at.desc())
        )
    )


@router.get("/cases/{case_id}/auth/export")
def export_auth(
    case_id: str,
    export_format: str = Query(default="json", alias="format", pattern="^(json|csv)$"),
    kind: str = Query(default="both", pattern="^(events|findings|both)$"),
    evidence_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    get_case_or_404(db, case_id)
    event_query = select(Event).where(
        Event.case_id == case_id, Event.parser_name == "auth_log"
    )
    if evidence_id:
        event_query = event_query.where(Event.evidence_id == evidence_id)
    events = list(
        db.scalars(
            event_query.order_by(
                Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc()
            )
        )
    )
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.case_id == case_id, Finding.category == "authentication")
            .options(selectinload(Finding.evidence_links))
            .order_by(Finding.created_at.desc())
        )
    )

    if export_format == "json":
        payload = {
            "case_id": case_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "parser": "auth_log",
            "events": (
                [
                    jsonable_encoder(EventRead.model_validate(event))
                    for event in events
                ]
                if kind in {"events", "both"}
                else []
            ),
            "findings": (
                [
                    jsonable_encoder(FindingRead.model_validate(finding))
                    for finding in findings
                ]
                if kind in {"findings", "both"}
                else []
            ),
            "limitations": [
                "Threshold-based authentication indicators are not proof of compromise.",
                "Timestamps may contain inferred years or assumed timezones.",
            ],
        }
        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": f'attachment; filename="auth_export_{case_id}.json"'
            },
        )

    buffer = io.StringIO()
    if kind in {"events", "both"}:
        writer = csv.DictWriter(
            buffer, fieldnames=EVENT_EXPORT_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        for event in events:
            attributes = event.attributes_json or {}
            writer.writerow(
                {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "timestamp_raw": event.timestamp_raw,
                    "timestamp_normalized": (
                        event.timestamp_normalized.isoformat()
                        if event.timestamp_normalized
                        else ""
                    ),
                    "timestamp_confidence": event.timestamp_confidence,
                    "source_filename": event.source_filename,
                    "source_locator": event.source_locator,
                    "source_ip": attributes.get("source_ip", ""),
                    "username": attributes.get("username", ""),
                    "auth_status": attributes.get("auth_status", ""),
                    "auth_method": attributes.get("auth_method", ""),
                    "pid": attributes.get("pid", ""),
                    "port": attributes.get("port", ""),
                    "invalid_user": attributes.get("invalid_user", ""),
                    "session_event": attributes.get("session_event", ""),
                    "target_user": attributes.get("sudo_target_user", ""),
                    "command": attributes.get("sudo_command", ""),
                }
            )

    if kind == "both":
        buffer.write("\n")

    if kind in {"findings", "both"}:
        finding_writer = csv.DictWriter(
            buffer, fieldnames=FINDING_EXPORT_FIELDS, extrasaction="ignore"
        )
        finding_writer.writeheader()
        for finding in findings:
            finding_writer.writerow(
                {
                    "finding_id": finding.id,
                    "severity": finding.severity,
                    "title": finding.title,
                    "status": finding.status,
                    "detection_method": finding.detection_method,
                    "confidence": finding.confidence,
                    "explanation": finding.explanation,
                    "limitations": finding.limitations,
                    "alternative_explanations": finding.alternative_explanations,
                    "evidence_links": " | ".join(
                        f"{link.evidence_id}:{link.source_locator}"
                        for link in finding.evidence_links
                    ),
                }
            )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="auth_export_{case_id}_{kind}.csv"'
            )
        },
    )
