from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Entity, Event, EventEntity
from ..utils.identifiers import normalize_entity


def get_or_create_entity(
    db: Session,
    case_id: str,
    entity_type: str,
    value_original: str,
    *,
    role: str = "mentioned",
) -> Entity | None:
    raw = (value_original or "").strip()
    if not raw:
        return None

    normalized, method = normalize_entity(entity_type, raw)
    existing = db.scalar(
        select(Entity).where(
            Entity.case_id == case_id,
            Entity.entity_type == entity_type,
            Entity.value_normalized == normalized,
        )
    )
    if existing:
        return existing

    entity = Entity(
        case_id=case_id,
        entity_type=entity_type,
        value_original=raw,
        value_normalized=normalized,
        normalization_method=method,
    )
    db.add(entity)
    db.flush()
    return entity


def link_event_entity(
    db: Session,
    event: Event,
    entity: Entity | None,
    *,
    role: str,
    raw_value: str,
) -> None:
    if entity is None:
        return
    existing = db.get(EventEntity, (event.id, entity.id, role))
    if existing:
        return
    db.add(
        EventEntity(
            event_id=event.id,
            entity_id=entity.id,
            role=role,
            raw_value=raw_value[:512],
        )
    )
    db.flush()
