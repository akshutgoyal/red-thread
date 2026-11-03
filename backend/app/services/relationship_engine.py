from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..models import Event, EventEntity
from ..utils.geo import haversine_meters, parse_coordinates
from . import relationship_service

ENGINE_VERSION = "deterministic_correlation_v1"
IDENTIFIER_TYPES = {
    "phone",
    "email",
    "ip",
    "device_id",
    "imei",
    "imsi",
    "mac",
    "account",
    "username",
    "camera_id",
    "upi_vpa",
    "utr",
    "transaction_id",
    "invoice_id",
    "gps_point",
}


def _locator(event: Event) -> str:
    return f"{event.source_filename}:{event.source_locator}"


def _support(event: Event, support_kind: str) -> dict[str, Any]:
    return {
        "evidence_id": event.evidence_id,
        "event_id": event.id,
        "source_locator": event.source_locator,
        "snippet": (event.source_snippet or "")[:800],
        "support_kind": support_kind,
    }


def _pair(left: Event, right: Event) -> tuple[Event, Event]:
    return tuple(sorted((left, right), key=lambda event: event.id))  # type: ignore[return-value]


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add(
    db: Session,
    *,
    case_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    correlation_rule: str,
    explanation: str,
    confidence: str,
    classification: str,
    metadata: dict[str, Any],
    supports: list[dict[str, Any]],
) -> None:
    relationship_service.upsert_relationship(
        db,
        case_id=case_id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship_type=relationship_type,
        correlation_rule=correlation_rule,
        explanation=explanation,
        confidence=confidence,
        classification=classification,
        metadata=metadata,
        supports=supports,
        commit=False,
    )


def _load_events(db: Session, case_id: str) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id)
            .options(
                selectinload(Event.entity_links).selectinload(EventEntity.entity)
            )
            .order_by(Event.created_at.asc(), Event.id.asc())
        )
    )


def build_case_relationships(db: Session, case_id: str) -> dict[str, int]:
    """Build deterministic, provenance-backed relationships for one case.

    These are correlation candidates, not identity or guilt conclusions. Every
    relationship carries the actual evidence/event locators that produced it.
    """
    settings = get_settings()
    temporal_window = max(1, settings.correlation_temporal_window_minutes) * 60
    spatial_window = max(1, settings.correlation_spatial_window_minutes) * 60
    spatial_radius = max(1, settings.correlation_spatial_radius_m)
    max_pairs = max(1, settings.correlation_max_pairs_per_identifier)

    events = _load_events(db, case_id)
    if not events:
        return {"relationships": 0, "relationship_supports": 0}

    events_by_entity: dict[str, list[Event]] = defaultdict(list)
    entities: dict[str, Any] = {}
    for event in events:
        seen_entities: set[str] = set()
        for link in event.entity_links:
            entity = link.entity
            if entity is None or entity.id in seen_entities:
                continue
            seen_entities.add(entity.id)
            events_by_entity[entity.id].append(event)
            entities[entity.id] = entity

    relationship_count = 0
    support_count = 0

    # A. Exact identifier matching across evidence sources.
    for entity_id, linked_events in events_by_entity.items():
        entity = entities[entity_id]
        if entity.entity_type not in IDENTIFIER_TYPES:
            continue
        by_evidence: dict[str, list[Event]] = defaultdict(list)
        for event in linked_events:
            by_evidence[event.evidence_id].append(event)
        if len(by_evidence) < 2:
            continue
        evidence_ids = sorted(by_evidence)
        candidates: list[tuple[Event, Event]] = []
        for left_id, right_id in combinations(evidence_ids, 2):
            for left in by_evidence[left_id][:5]:
                for right in by_evidence[right_id][:5]:
                    candidates.append((left, right))
                    if len(candidates) >= max_pairs:
                        break
                if len(candidates) >= max_pairs:
                    break
            if len(candidates) >= max_pairs:
                break
        for left, right in candidates:
            source, target = _pair(left, right)
            supports = [
                _support(source, f"{entity.entity_type}_mention"),
                _support(target, f"{entity.entity_type}_mention"),
            ]
            _add(
                db,
                case_id=case_id,
                source_type="event",
                source_id=source.id,
                target_type="event",
                target_id=target.id,
                relationship_type="shared_identifier",
                correlation_rule=f"exact_{entity.entity_type}_match",
                explanation=(
                    f"Exact normalized {entity.entity_type} identifier match: "
                    f"{entity.value_original!r} appears in {_locator(source)} and "
                    f"{_locator(target)}. This is a correlation candidate, not proof "
                    "that the same real-world actor produced both records."
                ),
                confidence="high",
                classification="correlation",
                metadata={
                    "engine": ENGINE_VERSION,
                    "entity_id": entity.id,
                    "entity_type": entity.entity_type,
                    "value": entity.value_original,
                    "normalized_value": entity.value_normalized,
                    "evidence_ids": sorted({source.evidence_id, target.evidence_id}),
                },
                supports=supports,
            )
            relationship_count += 1
            support_count += len(supports)

    # B. Entity co-mentions within the same event. This is an observation.
    co_mentions: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        unique_entities = {
            link.entity_id: link.entity for link in event.entity_links if link.entity is not None
        }
        entity_ids = sorted(unique_entities)
        for left_id, right_id in combinations(entity_ids, 2):
            key = (left_id, right_id)
            entry = co_mentions.setdefault(
                key,
                {
                    "left": unique_entities[left_id],
                    "right": unique_entities[right_id],
                    "supports": {},
                },
            )
            entry["supports"][event.id] = _support(event, "co_mention")

    for (left_id, right_id), entry in co_mentions.items():
        left = entry["left"]
        right = entry["right"]
        supports = list(entry["supports"].values())
        locators = "; ".join(
            f"{support['source_locator']}" for support in supports[:5]
        )
        _add(
            db,
            case_id=case_id,
            source_type="entity",
            source_id=left_id,
            target_type="entity",
            target_id=right_id,
            relationship_type="co_mention",
            correlation_rule="co_occurrence_same_event",
            explanation=(
                f"{left.entity_type} {left.value_original!r} and "
                f"{right.entity_type} {right.value_original!r} are mentioned in "
                f"{len(supports)} shared event(s) ({locators}). This is an observation "
                "of co-occurrence, not evidence that the entities are related."
            ),
            confidence="low",
            classification="observation",
            metadata={
                "engine": ENGINE_VERSION,
                "left_entity_id": left.id,
                "left_entity_type": left.entity_type,
                "left_value": left.value_original,
                "right_entity_id": right.id,
                "right_entity_type": right.entity_type,
                "right_value": right.value_original,
            },
            supports=supports,
        )
        relationship_count += 1
        support_count += len(supports)

    # C. Temporal associations among events sharing an identifier.
    for entity_id, linked_events in events_by_entity.items():
        entity = entities[entity_id]
        if entity.entity_type not in IDENTIFIER_TYPES:
            continue
        timed = [event for event in linked_events if event.timestamp_normalized is not None]
        timed.sort(key=lambda event: (_aware(event.timestamp_normalized), event.id))
        created = 0
        for left, right in combinations(timed, 2):
            delta = abs(
                (
                    _aware(right.timestamp_normalized)
                    - _aware(left.timestamp_normalized)
                ).total_seconds()
            )
            if delta > temporal_window:
                continue
            source, target = _pair(left, right)
            supports = [
                _support(source, "temporal_anchor"),
                _support(target, "temporal_related"),
            ]
            _add(
                db,
                case_id=case_id,
                source_type="event",
                source_id=source.id,
                target_type="event",
                target_id=target.id,
                relationship_type="temporal_association",
                correlation_rule="temporal_window_same_identifier",
                explanation=(
                    f"Events at {_locator(source)} and {_locator(target)} share "
                    f"{entity.entity_type} {entity.value_original!r} and are "
                    f"{delta / 60:.1f} minutes apart (window "
                    f"{temporal_window / 60:.0f} minutes). Temporal proximity is not "
                    "causation and does not establish identity."
                ),
                confidence="medium",
                classification="correlation",
                metadata={
                    "engine": ENGINE_VERSION,
                    "entity_id": entity.id,
                    "entity_type": entity.entity_type,
                    "value": entity.value_original,
                    "delta_seconds": round(delta, 3),
                    "window_seconds": temporal_window,
                },
                supports=supports,
            )
            relationship_count += 1
            support_count += len(supports)
            created += 1
            if created >= max_pairs:
                break

    # D. Spatial proximity between documented event coordinates.
    located: list[tuple[Event, tuple[float, float]]] = []
    for event in events:
        attributes = event.attributes_json or {}
        point = parse_coordinates(attributes.get("latitude"), attributes.get("longitude"))
        if point is not None:
            located.append((event, point))

    spatial_created = 0
    for (left, left_point), (right, right_point) in combinations(located, 2):
        if left.evidence_id == right.evidence_id:
            continue
        if left.timestamp_normalized is None or right.timestamp_normalized is None:
            continue
        delta = abs(
            (
                _aware(right.timestamp_normalized)
                - _aware(left.timestamp_normalized)
            ).total_seconds()
        )
        if delta > spatial_window:
            continue
        distance = haversine_meters(left_point, right_point)
        if distance > spatial_radius:
            continue
        source, target = _pair(left, right)
        supports = [
            _support(source, "location_observation"),
            _support(target, "location_observation"),
        ]
        _add(
            db,
            case_id=case_id,
            source_type="event",
            source_id=source.id,
            target_type="event",
            target_id=target.id,
            relationship_type="spatial_proximity",
            correlation_rule="spatial_window_proximity",
            explanation=(
                f"Documented coordinates at {_locator(source)} and "
                f"{_locator(target)} are {distance:.0f} m apart and "
                f"{delta / 60:.1f} minutes apart (radius {spatial_radius} m, window "
                f"{spatial_window / 60:.0f} minutes). Proximity is a correlation "
                "candidate, not proof of co-location or causation."
            ),
            confidence="medium",
            classification="correlation",
            metadata={
                "engine": ENGINE_VERSION,
                "distance_m": round(distance, 3),
                "delta_seconds": round(delta, 3),
                "radius_m": spatial_radius,
                "window_seconds": spatial_window,
                "source_point": left_point,
                "target_point": right_point,
            },
            supports=supports,
        )
        relationship_count += 1
        support_count += len(supports)
        spatial_created += 1
        if spatial_created >= max_pairs:
            break

    db.flush()
    return {
        "relationships": relationship_count,
        "relationship_supports": support_count,
    }
