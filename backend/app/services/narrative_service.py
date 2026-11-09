from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    Event,
    EventEntity,
    Evidence,
    Finding,
    FindingEvidence,
    Relationship,
    Report,
    ReviewDecision,
)
from ..schemas.guidance import (
    EventReviewListResponse,
    EventReviewRead,
    FindingEntityRef,
    FindingTimelineRef,
    NarrativeItem,
    NarrativeResponse,
    TimelineEventMeta,
    TimelineExtras,
    TimelineGroup,
)
from ..schemas.guidance import EventReviewRequest
from . import audit_service

NARRATIVE_DISCLAIMER = (
    "These statements are extracted observations and recorded analyst decisions. "
    "They are not a proven sequence of events and do not establish guilt, fraud or "
    "a criminal act. Open each reference and verify it against the original record."
)

EVENT_REVIEW_DECISIONS = {"relevant", "not_relevant", "needs_review"}
SUSPICIOUS_SEVERITIES = {"high", "critical"}

EVENT_TYPE_LABELS = {
    "call": "call record",
    "sms": "message",
    "message": "message",
    "chat": "chat message",
    "email": "email",
    "auth": "authentication event",
    "auth_login": "sign-in event",
    "device": "device event",
    "transaction": "transaction",
    "payment": "payment",
    "gps": "location fix",
    "cctv": "CCTV record",
    "image": "image record",
    "generic": "record",
}


def _event_label(event: Event) -> str:
    for prefix, label in EVENT_TYPE_LABELS.items():
        if event.event_type.startswith(prefix):
            return label
    return event.event_type.replace("_", " ")


def _fmt_ts(value: datetime | None) -> str:
    if value is None:
        return "an undated record"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def review_event(
    db: Session,
    case_id: str,
    event_id: str,
    payload: EventReviewRequest,
) -> EventReviewRead:
    if payload.decision not in EVENT_REVIEW_DECISIONS:
        raise ValueError(f"Unsupported event review decision: {payload.decision}")
    event = db.get(Event, event_id)
    if event is None or event.case_id != case_id:
        raise ValueError("Event not found in this case.")

    decision = ReviewDecision(
        case_id=case_id,
        target_type="event",
        target_id=event.id,
        decision=payload.decision,
        reviewer=payload.reviewer,
        note=payload.note,
    )
    db.add(decision)
    audit_service.record(
        db,
        case_id,
        "event.reviewed",
        evidence_id=event.evidence_id,
        details={
            "event_id": event.id,
            "decision": payload.decision,
            "reviewer": payload.reviewer,
            "note": payload.note,
        },
    )
    db.commit()
    db.refresh(decision)
    return EventReviewRead(
        event_id=event.id,
        decision=decision.decision,
        reviewer=decision.reviewer,
        note=decision.note,
        reviewed_at=decision.created_at,
    )


def list_event_reviews(db: Session, case_id: str) -> EventReviewListResponse:
    rows = list(
        db.scalars(
            select(ReviewDecision)
            .where(
                ReviewDecision.case_id == case_id,
                ReviewDecision.target_type == "event",
            )
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    latest: dict[str, ReviewDecision] = {}
    for row in rows:
        latest[row.target_id] = row
    items = [
        EventReviewRead(
            event_id=row.target_id,
            decision=row.decision,
            reviewer=row.reviewer,
            note=row.note,
            reviewed_at=row.created_at,
        )
        for row in latest.values()
    ]
    return EventReviewListResponse(items=items, total=len(items))


def latest_event_review_map(db: Session, case_id: str) -> dict[str, str]:
    rows = list(
        db.scalars(
            select(ReviewDecision)
            .where(
                ReviewDecision.case_id == case_id,
                ReviewDecision.target_type == "event",
            )
            .order_by(ReviewDecision.created_at.asc())
        )
    )
    latest: dict[str, str] = {}
    for row in rows:
        latest[row.target_id] = row.decision
    return latest


def timeline_extras(
    db: Session,
    case_id: str,
    events: list[Event],
) -> TimelineExtras:
    """Attach finding/relationship context and correlated groups to a timeline."""

    if not events:
        return TimelineExtras()

    event_ids = {event.id for event in events}
    event_by_id = {event.id: event for event in events}

    finding_rows = list(
        db.scalars(
            select(Finding)
            .where(Finding.case_id == case_id)
            .options(selectinload(Finding.evidence_links))
        )
    )
    finding_ids_by_event: dict[str, list[str]] = defaultdict(list)
    suspicious_events: set[str] = set()
    for finding in finding_rows:
        for link in finding.evidence_links:
            if link.event_id and link.event_id in event_ids:
                if finding.id not in finding_ids_by_event[link.event_id]:
                    finding_ids_by_event[link.event_id].append(finding.id)
                if finding.severity in SUSPICIOUS_SEVERITIES:
                    suspicious_events.add(link.event_id)

    relationships = list(
        db.scalars(
            select(Relationship)
            .where(Relationship.case_id == case_id)
            .options(selectinload(Relationship.supports))
        )
    )
    relationship_ids_by_event: dict[str, list[str]] = defaultdict(list)
    groups: list[TimelineGroup] = []
    for relationship in relationships:
        support_event_ids = [
            support.event_id
            for support in relationship.supports
            if support.event_id and support.event_id in event_ids
        ]
        for event_id in support_event_ids:
            if relationship.id not in relationship_ids_by_event[event_id]:
                relationship_ids_by_event[event_id].append(relationship.id)
        if relationship.review_status == "rejected":
            suspicious_events.update(support_event_ids)
        unique_event_ids = list(dict.fromkeys(support_event_ids))
        if len(unique_event_ids) >= 2 and len(groups) < 50:
            timestamps = [
                event_by_id[event_id].timestamp_normalized
                for event_id in unique_event_ids
                if event_by_id[event_id].timestamp_normalized is not None
            ]
            groups.append(
                TimelineGroup(
                    id=relationship.id,
                    title=_group_title(relationship),
                    explanation=relationship.explanation,
                    event_ids=unique_event_ids,
                    relationship_id=relationship.id,
                    classification=relationship.classification,
                    confidence=relationship.confidence,
                    start=min(timestamps) if timestamps else None,
                    end=max(timestamps) if timestamps else None,
                )
            )
    groups.sort(key=lambda item: item.start or datetime.min.replace(tzinfo=timezone.utc))

    reviews = latest_event_review_map(db, case_id)
    meta = {
        event.id: TimelineEventMeta(
            finding_ids=finding_ids_by_event.get(event.id, []),
            relationship_ids=relationship_ids_by_event.get(event.id, []),
            review_status=reviews.get(event.id),
            suspicious=event.id in suspicious_events,
        )
        for event in events
    }
    return TimelineExtras(event_meta=meta, groups=groups)


def _group_title(relationship: Relationship) -> str:
    labels = {
        "communication_sequence": "Communication sequence",
        "temporal_association": "Events close in time",
        "spatial_proximity": "Documented nearby",
        "shared_identifier": "Shared identifier",
        "co_mention": "Appears in the same event",
        "device_auth_context": "Device or sign-in context",
    }
    return labels.get(relationship.relationship_type, "Connected events")


def build_narrative(db: Session, case_id: str) -> NarrativeResponse:
    """Build an evidence-linked chronological summary without an LLM."""

    events = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id)
            .options(selectinload(Event.entity_links).selectinload(EventEntity.entity))
            .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc())
            .limit(500)
        )
    )
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.case_id == case_id)
            .options(selectinload(Finding.evidence_links))
            .order_by(Finding.created_at.asc())
        )
    )
    relationships = list(
        db.scalars(
            select(Relationship)
            .where(Relationship.case_id == case_id)
            .order_by(Relationship.created_at.asc())
        )
    )
    reports = list(
        db.scalars(
            select(Report).where(Report.case_id == case_id).order_by(Report.generated_at.asc())
        )
    )
    reviewed_relationships = [
        item for item in relationships if item.review_status not in ("unreviewed", None, "")
    ]

    items: list[NarrativeItem] = []
    index = 1

    # Group events into 5-minute buckets so the narrative reads as a sequence
    # rather than one line per row.
    buckets: dict[tuple, list[Event]] = {}
    for event in events:
        if event.timestamp_normalized is None:
            continue
        stamp = event.timestamp_normalized.astimezone(timezone.utc)
        bucket_start = stamp.replace(
            minute=(stamp.minute // 5) * 5, second=0, microsecond=0
        )
        buckets.setdefault((bucket_start, event.event_type), []).append(event)

    for (bucket_start, event_type), bucket_events in sorted(
        buckets.items(), key=lambda item: item[0][0]
    ):
        first = bucket_events[0]
        values = _distinct_entity_values(bucket_events)
        count = len(bucket_events)
        label = _event_label(first)
        statement = (
            f"{_fmt_ts(bucket_start)}: {count} {label}"
            f"{'s' if count != 1 else ''} recorded"
        )
        if values:
            statement += f" involving {_join_values(values)}"
        statement += f" (source: {first.source_filename})."
        items.append(
            NarrativeItem(
                index=index,
                statement=statement,
                kind="observation",
                timestamp=bucket_start,
                event_ids=[event.id for event in bucket_events],
                evidence_ids=list({event.evidence_id for event in bucket_events}),
                href=f"/cases/{case_id}/timeline?event={first.id}",
            )
        )
        index += 1

    undated = [event for event in events if event.timestamp_normalized is None]
    if undated:
        items.append(
            NarrativeItem(
                index=index,
                statement=(
                    f"{len(undated)} records have no reliable timestamp and are listed "
                    "separately in the timeline."
                ),
                kind="observation",
                event_ids=[event.id for event in undated],
                evidence_ids=list({event.evidence_id for event in undated}),
                href=f"/cases/{case_id}/timeline",
            )
        )
        index += 1

    for finding in findings:
        if finding.severity not in SUSPICIOUS_SEVERITIES:
            continue
        evidence_ids = [link.evidence_id for link in finding.evidence_links]
        event_ids = [link.event_id for link in finding.evidence_links if link.event_id]
        status_text = {
            "accepted": "was accepted for review",
            "rejected": "was rejected after review",
            "needs_more_evidence": "needs further evidence",
            "needs_review": "still needs review",
            "open": "has not been reviewed",
        }.get(finding.status, "has not been reviewed")
        items.append(
            NarrativeItem(
                index=index,
                statement=(
                    f"A {finding.severity}-severity finding, \"{finding.title}\", {status_text}. "
                    f"{finding.explanation}"
                ),
                kind="finding",
                finding_ids=[finding.id],
                evidence_ids=evidence_ids,
                event_ids=event_ids,
                timestamp=finding.created_at,
                href=f"/cases/{case_id}/findings?finding={finding.id}",
            )
        )
        index += 1

    for relationship in reviewed_relationships:
        items.append(
            NarrativeItem(
                index=index,
                statement=(
                    f"A {relationship.relationship_type.replace('_', ' ')} link between "
                    f"{relationship.source_type} and {relationship.target_type} was "
                    f"{relationship.review_status.replace('_', ' ')} by an investigator. "
                    "It remains a correlation, not proof."
                ),
                kind="review",
                relationship_ids=[relationship.id],
                href=f"/cases/{case_id}/graph?relationship={relationship.id}",
            )
        )
        index += 1

    for report in reports:
        items.append(
            NarrativeItem(
                index=index,
                statement=(
                    f"A {report.report_type.upper()} draft report was generated on "
                    f"{_fmt_ts(report.generated_at)}. It reflects the records stored at "
                    "that time."
                ),
                kind="report",
                timestamp=report.generated_at,
                href=f"/cases/{case_id}/reports",
            )
        )
        index += 1

    return NarrativeResponse(
        case_id=case_id,
        generated_at=datetime.now(timezone.utc),
        items=items,
        disclaimer=NARRATIVE_DISCLAIMER,
    )


def _distinct_entity_values(events: list[Event]) -> list[str]:
    values: list[str] = []
    for event in events:
        for link in event.entity_links:
            if link.entity is None:
                continue
            value = link.entity.value_original
            if value not in values:
                values.append(value)
    return values[:4]


def _join_values(values: list[str]) -> str:
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])} and {values[-1]}"


def finding_context(
    db: Session,
    case_id: str,
    finding: Finding,
) -> tuple[list[FindingEntityRef], list[FindingTimelineRef]]:
    """Return related entities and timeline references for a finding."""

    event_ids = [link.event_id for link in finding.evidence_links if link.event_id]
    if not event_ids:
        return [], []

    events = list(
        db.scalars(
            select(Event)
            .where(Event.id.in_(event_ids), Event.case_id == case_id)
            .options(selectinload(Event.entity_links).selectinload(EventEntity.entity))
        )
    )
    entity_refs: list[FindingEntityRef] = []
    timeline_refs: list[FindingTimelineRef] = []
    seen_entities: set[tuple[str, str | None]] = set()
    for event in events:
        timeline_refs.append(
            FindingTimelineRef(
                event_id=event.id,
                timestamp_normalized=event.timestamp_normalized,
                event_type=event.event_type,
            )
        )
        for link in event.entity_links:
            entity = link.entity
            if entity is None:
                continue
            key = (entity.id, event.id)
            if key in seen_entities:
                continue
            seen_entities.add(key)
            entity_refs.append(
                FindingEntityRef(
                    entity_id=entity.id,
                    entity_type=entity.entity_type,
                    value=entity.value_original,
                    event_id=event.id,
                )
            )
    return entity_refs[:12], timeline_refs[:12]
