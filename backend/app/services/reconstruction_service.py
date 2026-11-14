"""Unified event sequence for the Crime Reconstruction workspace.

This deliberately introduces no new data store. Every item is an existing
record: the sequence is the timeline's own events, joined to the entity links,
relationship supports, finding links and review decisions that already exist.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models.event import Entity, Event, EventEntity
from ..models.finding import Finding, FindingEvidence
from ..models.relationship import Relationship, ReviewDecision
from ..schemas.reconstruction import (
    ReconstructionSequenceResponse,
    SequenceEntity,
    SequenceEvent,
    SequenceGap,
    SequenceRelationship,
)
from . import narrative_service

DESCRIPTION_BY_PREFIX = {
    "call": "Call record",
    "sms": "Text message",
    "message": "Message",
    "chat": "Chat message",
    "email": "Email",
    "transaction": "Financial transaction",
    "payment": "Payment record",
    "invoice": "Invoice record",
    "auth": "Authentication activity",
    "login": "Sign-in activity",
    "device": "Device activity",
    "registry": "Device registry entry",
    "usb": "Removable device event",
    "gps": "Location observation",
    "location": "Location observation",
    "cctv": "CCTV segment",
    "image": "Image record",
}

CATEGORY_BY_PREFIX = {
    "call": "communication",
    "sms": "communication",
    "message": "communication",
    "chat": "communication",
    "email": "communication",
    "transaction": "financial",
    "payment": "financial",
    "invoice": "financial",
    "auth": "authentication",
    "login": "authentication",
    "device": "device",
    "registry": "device",
    "usb": "device",
    "gps": "location",
    "location": "location",
    "cctv": "visual",
    "image": "visual",
}

CONFIDENCE_BY_TIMESTAMP = {
    "exact": "documented",
    "high": "documented",
    "medium": "supported",
    "estimated": "correlated",
    "approximate": "correlated",
    "ambiguous": "correlated",
    "low": "correlated",
    "unknown": "uncertain",
}


def _description(event: Event) -> str:
    """Describe an event from its parsed attributes, never from raw JSON."""

    attributes = event.attributes_json or {}
    kind = event.event_type.lower()

    def value(*keys: str) -> str:
        for key in keys:
            candidate = attributes.get(key)
            if candidate is None or candidate == "":
                continue
            if isinstance(candidate, float):
                return f"{candidate:g}"
            return str(candidate).strip()
        return ""

    if kind.startswith("call"):
        caller, receiver = value("caller", "caller_id"), value("receiver", "receiver_id")
        duration = value("duration_sec", "duration_seconds")
        parts = []
        if caller and receiver:
            parts.append(f"Call from {caller} to {receiver}")
        elif caller:
            parts.append(f"Call involving {caller}")
        call_type = value("call_type")
        if call_type:
            parts.append(f"({call_type.lower()})")
        if duration:
            parts.append(f"lasting {duration}s")
        tower = value("cell_tower_id")
        if tower:
            parts.append(f"via cell tower {tower}")
        return " ".join(parts) or "Call record"

    if kind.startswith(("sms", "message", "chat")):
        sender, recipient = value("sender"), value("recipient", "receiver")
        body = value("message", "body", "text")
        parts = []
        if sender and recipient:
            parts.append(f"Message from {sender} to {recipient}")
        elif sender:
            parts.append(f"Message from {sender}")
        elif recipient:
            parts.append(f"Message to {recipient}")
        else:
            parts.append("Message")
        if body:
            parts.append(f'reading "{body[:220]}"')
        attachment = value("attachment")
        if attachment:
            parts.append(f"with attachment {attachment}")
        return " ".join(parts)

    if kind.startswith("email"):
        subject = value("subject")
        sender = value("from", "sender")
        recipient = value("to", "recipient")
        parts = []
        if sender and recipient:
            parts.append(f"Email from {sender} to {recipient}")
        else:
            parts.append("Email")
        if subject:
            parts.append(f'subject "{subject[:160]}"')
        return " ".join(parts)

    if kind.startswith(("transaction", "payment", "invoice")):
        amount = value("amount", "value")
        currency = value("currency")
        payer = value("payer", "from", "sender")
        payee = value("payee", "to", "receiver")
        reference = value("utr", "reference", "transaction_id", "invoice_id")
        parts = []
        if amount:
            parts.append(f"{currency + ' ' if currency else ''}{amount} transfer".strip())
        else:
            parts.append("Financial record")
        if payer and payee:
            parts.append(f"from {payer} to {payee}")
        if reference:
            parts.append(f"reference {reference}")
        return " ".join(parts)

    if kind.startswith(("auth", "login")):
        status = value("auth_status", "status")
        user = value("user", "username", "account", "invalid_user")
        method = value("auth_method", "method")
        source_ip = value("ip", "source_ip", "remote_ip")
        parts = ["Authentication"]
        if status:
            parts.append(status)
        if user and user.lower() not in {"true", "false"}:
            parts.append(f"for {user}")
        if method:
            parts.append(f"using {method}")
        if source_ip:
            parts.append(f"from {source_ip}")
        return " ".join(parts)

    if kind.startswith(("gps", "location")):
        place = value("place", "site_name")
        latitude, longitude = value("latitude"), value("longitude")
        accuracy = value("accuracy_m")
        parts = ["Location observation"]
        if place:
            parts.append(f"at {place}")
        if latitude and longitude:
            parts.append(f"({latitude}, {longitude})")
        if accuracy:
            parts.append(f"accurate to {accuracy}m")
        source = value("coordinate_source")
        if source:
            parts.append(f"source: {source}")
        return " ".join(parts)

    if kind.startswith(("cctv", "image")):
        camera = value("camera_id", "device_id")
        place = value("place", "site_name")
        start, end = value("recording_start"), value("recording_end")
        parts = ["CCTV recording"]
        if camera:
            parts.append(f"from {camera}")
        if place:
            parts.append(f"at {place}")
        if start and end:
            parts.append(f"covering {start} to {end}")
        return " ".join(parts)

    if kind.startswith(("device", "registry", "usb")):
        device = value("device_id", "imei")
        activity = value("activity", "event")
        account = value("account", "phone", "user")
        source_ip = value("ip")
        parts = ["Device activity"]
        if activity:
            parts.append(activity.replace("_", " "))
        if device:
            parts.append(f"on {device}")
        if account:
            parts.append(f"account {account}")
        if source_ip:
            parts.append(f"ip {source_ip}")
        return " ".join(parts)

    summary = value("summary", "description", "activity")
    if summary:
        return summary[:400]
    return f"Record in {event.source_filename} at {event.source_locator}"


def _category(event_type: str) -> str:
    lowered = event_type.lower()
    for prefix, category in CATEGORY_BY_PREFIX.items():
        if lowered.startswith(prefix):
            return category
    return "other"


def _confidence(event: Event) -> tuple[str, str]:
    if event.timestamp_normalized is None:
        return (
            "uncertain",
            "The record carries no usable timestamp, so it cannot be placed in sequence.",
        )
    base = CONFIDENCE_BY_TIMESTAMP.get(event.timestamp_confidence, "uncertain")
    basis = (event.attributes_json or {}).get("timestamp_basis")
    if base == "documented":
        return base, "The timestamp was parsed directly from the source record."
    reason = "The timestamp was normalised from the source record and should be confirmed."
    if isinstance(basis, str) and basis:
        reason = f"{reason} Basis: {basis}."
    if event.timestamp_confidence in {"estimated", "approximate", "ambiguous", "low"}:
        return (
            "correlated",
            "The timestamp is approximate, so ordering against other records is indicative only."
            + (f" Basis: {basis}." if isinstance(basis, str) and basis else ""),
        )
    return base, reason


def build_sequence(
    db: Session,
    case_id: str,
    *,
    limit: int = 1000,
    evidence_id: str | None = None,
    event_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> ReconstructionSequenceResponse:
    filters = [Event.case_id == case_id]
    if evidence_id:
        filters.append(Event.evidence_id == evidence_id)
    if event_type:
        filters.append(Event.event_type == event_type)
    if start:
        filters.append(Event.timestamp_normalized >= _parse(start))
    if end:
        filters.append(Event.timestamp_normalized <= _parse(end))

    events = list(
        db.scalars(
            select(Event)
            .where(*filters)
            .options(
                selectinload(Event.entity_links).selectinload(EventEntity.entity),
                selectinload(Event.finding_links),
            )
            .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc())
            .limit(limit)
        )
    )
    if not events:
        return ReconstructionSequenceResponse(
            case_id=case_id,
            items=[],
            undated=[],
            total=0,
            limitations=[
                "No parsed events are available yet. Upload and process evidence first.",
            ],
        )

    event_ids = {event.id for event in events}
    event_by_id = {event.id: event for event in events}

    entity_by_id = {
        entity.id: entity
        for entity in db.scalars(
            select(Entity).where(Entity.case_id == case_id)
        )
    }

    finding_ids_by_event: dict[str, list[str]] = defaultdict(list)
    for link in db.scalars(
        select(FindingEvidence).where(FindingEvidence.event_id.in_(event_ids))
    ):
        if link.event_id and link.finding_id not in finding_ids_by_event[link.event_id]:
            finding_ids_by_event[link.event_id].append(link.finding_id)

    relationships_by_event: dict[str, list[Relationship]] = defaultdict(list)
    relationships = list(
        db.scalars(
            select(Relationship)
            .where(Relationship.case_id == case_id)
            .options(selectinload(Relationship.supports))
        )
    )
    for relationship in relationships:
        for support in relationship.supports:
            if support.event_id and support.event_id in event_ids:
                if relationship not in relationships_by_event[support.event_id]:
                    relationships_by_event[support.event_id].append(relationship)

    latest_reviews: dict[str, ReviewDecision] = {}
    for review in db.scalars(
        select(ReviewDecision)
        .where(
            ReviewDecision.case_id == case_id,
            ReviewDecision.target_type == "event",
        )
        .order_by(ReviewDecision.created_at.asc())
    ):
        latest_reviews[review.target_id] = review

    extras = narrative_service.timeline_extras(db, case_id, events)
    group_ids_by_event: dict[str, list[str]] = defaultdict(list)
    for group in extras.groups:
        for event_id in group.event_ids:
            group_ids_by_event[event_id].append(group.id)

    items: list[SequenceEvent] = []
    undated: list[SequenceEvent] = []
    categories: dict[str, int] = defaultdict(int)

    for event in events:
        confidence, confidence_reason = _confidence(event)
        review = latest_reviews.get(event.id)
        category = _category(event.event_type)
        categories[category] += 1

        entities = []
        for link in event.entity_links:
            entity = entity_by_id.get(link.entity_id) or link.entity
            if entity is None:
                continue
            entities.append(
                SequenceEntity(
                    id=entity.id,
                    entity_type=entity.entity_type,
                    value=entity.value_original,
                    role=link.role,
                )
            )

        related = []
        for relationship in relationships_by_event.get(event.id, []):
            counterpart_type, counterpart_value = _counterpart(
                relationship, event, entity_by_id, event_by_id
            )
            related.append(
                SequenceRelationship(
                    id=relationship.id,
                    relationship_type=relationship.relationship_type,
                    explanation=relationship.explanation,
                    confidence=relationship.confidence,
                    classification=relationship.classification,
                    review_status=relationship.review_status,
                    counterpart_type=counterpart_type,
                    counterpart_value=counterpart_value,
                )
            )

        item = SequenceEvent(
            id=event.id,
            timestamp=event.timestamp_normalized,
            timestamp_raw=event.timestamp_raw,
            timestamp_confidence=event.timestamp_confidence,
            timestamp_timezone=event.timestamp_timezone,
            event_type=event.event_type,
            category=category,
            label=narrative_service._event_label(event),
            description=_description(event),
            evidence_id=event.evidence_id,
            source_filename=event.source_filename,
            source_locator=event.source_locator,
            source_snippet=event.source_snippet,
            entities=entities,
            relationships=related,
            finding_ids=finding_ids_by_event.get(event.id, []),
            review_status=review.decision if review else "unreviewed",
            review_note=review.note if review else "",
            group_ids=group_ids_by_event.get(event.id, []),
            confidence=confidence,
            confidence_reason=confidence_reason,
        )
        if event.timestamp_normalized is None:
            undated.append(item)
        else:
            items.append(item)

    return ReconstructionSequenceResponse(
        case_id=case_id,
        items=items,
        undated=undated,
        total=len(items) + len(undated),
        categories=dict(categories),
        groups=[
            {
                "id": group.id,
                "title": group.title,
                "explanation": group.explanation,
                "event_ids": group.event_ids,
                "classification": group.classification,
                "confidence": group.confidence,
                "start": group.start.isoformat() if group.start else None,
                "end": group.end.isoformat() if group.end else None,
            }
            for group in extras.groups
        ],
        gaps=_detect_gaps(items),
        limitations=[
            "Ordering is by the timestamp recorded in each source and does not on its own establish that one event caused another.",
            "Records without a usable timestamp are listed separately rather than placed in sequence.",
            "Categories are derived from the parser that produced each record.",
        ],
    )


def _counterpart(
    relationship: Relationship,
    event: Event,
    entity_by_id: dict[str, Entity],
    event_by_id: dict[str, Event],
) -> tuple[str, str]:
    """Resolve the other side of a relationship into something readable."""

    candidates = []
    if relationship.source_type == "entity":
        candidates.append(relationship.source_id)
    if relationship.target_type == "entity":
        candidates.append(relationship.target_id)
    for entity_id in candidates:
        entity = entity_by_id.get(entity_id)
        if entity is not None:
            return entity.entity_type, entity.value_original
    if candidates:
        return "entity", candidates[0]

    other_id = (
        relationship.target_id
        if relationship.source_id == event.id
        else relationship.source_id
    )
    other = event_by_id.get(other_id)
    if other is not None:
        return other.event_type, f"{narrative_service._event_label(other)} at {other.source_locator}"
    return relationship.source_type, relationship.source_id


def _detect_gaps(items: list[SequenceEvent], threshold_hours: int = 36) -> list[SequenceGap]:
    """Report silent periods, which are an absence of evidence rather than of activity."""

    gaps: list[SequenceGap] = []
    previous: SequenceEvent | None = None
    for item in items:
        if item.timestamp is None:
            continue
        if previous is not None and previous.timestamp is not None:
            delta: timedelta = item.timestamp - previous.timestamp
            if delta >= timedelta(hours=threshold_hours):
                gaps.append(
                    SequenceGap(
                        kind="silent_period",
                        message=(
                            f"No dated records between {_fmt(previous.timestamp)} and "
                            f"{_fmt(item.timestamp)}. This is an absence of evidence in "
                            "the uploaded sources, not proof that nothing happened."
                        ),
                        start=previous.timestamp,
                        end=item.timestamp,
                    )
                )
        previous = item
    return gaps


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
