from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AiQuery,
    AuditEvent,
    Case,
    Entity,
    Event,
    EventEntity,
    Evidence,
    Finding,
    FindingEvidence,
    GraphEdge,
    InvestigatorAnnotation,
    Relationship,
    RelationshipSupport,
    Report,
    ReviewDecision,
)
from . import storage_service

logger = logging.getLogger("uvicorn.error")


def _map_id(kind: str, value: str | None, maps: dict[str, dict[str, str]]) -> str | None:
    if value is None:
        return None
    return maps.get(kind, {}).get(value, value)


def _copy_storage(source_key: str, destination_key: str, content_type: str) -> None:
    try:
        data = b"".join(storage_service.iter_object(source_key))
        storage_service.save_bytes(destination_key, data, content_type=content_type)
    except Exception:  # noqa: BLE001 - a demo copy must not fail because one object is unavailable
        logger.exception("Demo copy: could not copy storage object %s", source_key)


def clone_case(db: Session, source: Case, demo_user_id: str) -> Case:
    """Deep-copy one synthetic template case for one demo visitor."""
    clone = Case(
        title=source.title,
        description=source.description,
        status=source.status,
        investigator_notes=source.investigator_notes,
        owner_id=demo_user_id,
        is_demo=True,
    )
    db.add(clone)
    db.flush()
    maps: dict[str, dict[str, str]] = {
        "evidence": {},
        "event": {},
        "entity": {},
        "finding": {},
        "relationship": {},
        "case": {source.id: clone.id},
    }

    # Evidence + stored objects.
    for item in db.scalars(select(Evidence).where(Evidence.case_id == source.id)):
        new_item = Evidence(
            case_id=clone.id,
            original_filename=item.original_filename,
            stored_filename=item.stored_filename,
            relative_path=item.relative_path,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            uploaded_at=item.uploaded_at,
            parser_name=item.parser_name,
            parser_version=item.parser_version,
            processing_status=item.processing_status,
            processing_error=item.processing_error,
            metadata_json=item.metadata_json,
            hash_verified=item.hash_verified,
            hash_verified_at=item.hash_verified_at,
        )
        db.add(new_item)
        db.flush()
        maps["evidence"][item.id] = new_item.id
        destination = storage_service.evidence_key(clone.id, item.stored_filename)
        _copy_storage(item.relative_path, destination, item.media_type)
        new_item.relative_path = destination

    # Events.
    for item in db.scalars(select(Event).where(Event.case_id == source.id)):
        new_item = Event(
            case_id=clone.id,
            evidence_id=_map_id("evidence", item.evidence_id, maps),
            event_type=item.event_type,
            timestamp_raw=item.timestamp_raw,
            timestamp_normalized=item.timestamp_normalized,
            timestamp_confidence=item.timestamp_confidence,
            timestamp_timezone=item.timestamp_timezone,
            source_filename=item.source_filename,
            source_locator=item.source_locator,
            source_snippet=item.source_snippet,
            attributes_json=item.attributes_json,
            warnings_json=item.warnings_json,
            parser_name=item.parser_name,
            parser_version=item.parser_version,
        )
        db.add(new_item)
        db.flush()
        maps["event"][item.id] = new_item.id

    # Entities.
    for item in db.scalars(select(Entity).where(Entity.case_id == source.id)):
        new_item = Entity(
            case_id=clone.id,
            entity_type=item.entity_type,
            value_original=item.value_original,
            value_normalized=item.value_normalized,
            normalization_method=item.normalization_method,
        )
        db.add(new_item)
        db.flush()
        maps["entity"][item.id] = new_item.id

    for item in db.scalars(
        select(EventEntity).where(EventEntity.event_id.in_(list(maps["event"].keys())))
    ):
        db.add(
            EventEntity(
                event_id=_map_id("event", item.event_id, maps),
                entity_id=_map_id("entity", item.entity_id, maps),
                role=item.role,
                raw_value=item.raw_value,
            )
        )

    # Findings.
    for item in db.scalars(select(Finding).where(Finding.case_id == source.id)):
        new_item = Finding(
            case_id=clone.id,
            severity=item.severity,
            category=item.category,
            title=item.title,
            explanation=item.explanation,
            detection_method=item.detection_method,
            confidence=item.confidence,
            status=item.status,
            limitations=item.limitations,
            alternative_explanations=item.alternative_explanations,
            reviewer_note=item.reviewer_note,
            reviewed_at=item.reviewed_at,
        )
        db.add(new_item)
        db.flush()
        maps["finding"][item.id] = new_item.id

    for item in db.scalars(
        select(FindingEvidence).where(
            FindingEvidence.finding_id.in_(list(maps["finding"].keys()))
        )
    ):
        db.add(
            FindingEvidence(
                finding_id=_map_id("finding", item.finding_id, maps),
                evidence_id=_map_id("evidence", item.evidence_id, maps),
                event_id=_map_id("event", item.event_id, maps),
                role=item.role,
                source_locator=item.source_locator,
            )
        )

    # Relationships and provenance supports.
    for item in db.scalars(select(Relationship).where(Relationship.case_id == source.id)):
        new_item = Relationship(
            case_id=clone.id,
            source_type=item.source_type,
            source_id=_map_id(item.source_type, item.source_id, maps),
            target_type=item.target_type,
            target_id=_map_id(item.target_type, item.target_id, maps),
            relationship_type=item.relationship_type,
            correlation_rule=item.correlation_rule,
            explanation=item.explanation,
            confidence=item.confidence,
            classification=item.classification,
            review_status=item.review_status,
            review_note=item.review_note,
            metadata_json=item.metadata_json,
        )
        db.add(new_item)
        db.flush()
        maps["relationship"][item.id] = new_item.id

    for item in db.scalars(
        select(RelationshipSupport).where(
            RelationshipSupport.relationship_id.in_(list(maps["relationship"].keys()))
        )
    ):
        db.add(
            RelationshipSupport(
                relationship_id=_map_id("relationship", item.relationship_id, maps),
                evidence_id=_map_id("evidence", item.evidence_id, maps),
                event_id=_map_id("event", item.event_id, maps),
                finding_id=_map_id("finding", item.finding_id, maps),
                source_locator=item.source_locator,
                snippet=item.snippet,
                support_kind=item.support_kind,
            )
        )

    # Legacy graph edges and their supporting identifiers.
    for item in db.scalars(select(GraphEdge).where(GraphEdge.case_id == source.id)):
        db.add(
            GraphEdge(
                case_id=clone.id,
                source_type=item.source_type,
                source_id=_map_id(item.source_type, item.source_id, maps),
                target_type=item.target_type,
                target_id=_map_id(item.target_type, item.target_id, maps),
                edge_type=item.edge_type,
                match_method=item.match_method,
                explanation=item.explanation,
                confidence=item.confidence,
                supporting_event_ids_json=[
                    _map_id("event", value, maps)
                    for value in (item.supporting_event_ids_json or [])
                ],
                supporting_evidence_ids_json=[
                    _map_id("evidence", value, maps)
                    for value in (item.supporting_evidence_ids_json or [])
                ],
            )
        )

    # Review and annotation history.
    for item in db.scalars(select(ReviewDecision).where(ReviewDecision.case_id == source.id)):
        db.add(
            ReviewDecision(
                case_id=clone.id,
                target_type=item.target_type,
                target_id=_map_id(item.target_type, item.target_id, maps),
                decision=item.decision,
                reviewer=item.reviewer,
                note=item.note,
            )
        )
    for item in db.scalars(
        select(InvestigatorAnnotation).where(InvestigatorAnnotation.case_id == source.id)
    ):
        db.add(
            InvestigatorAnnotation(
                case_id=clone.id,
                target_type=item.target_type,
                target_id=_map_id(item.target_type, item.target_id, maps),
                author=item.author,
                note=item.note,
            )
        )

    # Audit, AI history and reports.
    for item in db.scalars(select(AuditEvent).where(AuditEvent.case_id == source.id)):
        db.add(
            AuditEvent(
                case_id=clone.id,
                evidence_id=_map_id("evidence", item.evidence_id, maps),
                actor=item.actor,
                action=item.action,
                details_json=item.details_json,
            )
        )
    for item in db.scalars(select(AiQuery).where(AiQuery.case_id == source.id)):
        db.add(
            AiQuery(
                case_id=clone.id,
                question=item.question,
                provider=item.provider,
                model=item.model,
                answer=item.answer,
                citations_json=item.citations_json,
                validation_status=item.validation_status,
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                cached_tokens=item.cached_tokens,
                cost_usd=item.cost_usd,
                latency_ms=item.latency_ms,
            )
        )
    for item in db.scalars(select(Report).where(Report.case_id == source.id)):
        destination = storage_service.report_key(clone.id, item.filename)
        _copy_storage(item.relative_path, destination, "application/pdf" if item.report_type == "pdf" else "application/json")
        db.add(
            Report(
                case_id=clone.id,
                report_type=item.report_type,
                filename=item.filename,
                relative_path=destination,
                status=item.status,
                metadata_json=item.metadata_json,
            )
        )

    db.commit()
    db.refresh(clone)
    return clone


def clone_demo_templates(db: Session, demo_user_id: str) -> list[Case]:
    templates = list(
        db.scalars(
            select(Case).where(Case.is_demo.is_(True), Case.owner_id.is_(None))
        )
    )
    return [clone_case(db, template, demo_user_id) for template in templates]
