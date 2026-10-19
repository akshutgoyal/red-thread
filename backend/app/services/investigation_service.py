from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Event, Evidence, Finding, FindingEvidence
from ..parsers.base import CanonicalEventDraft, ParserContext, ParseResult
from ..parsers.registry import SUPPORTED_DESCRIPTION, detect_parser
from . import audit_service, entity_service, evidence_service, reconciliation_service


def _parser_context(evidence: Evidence, parser_name: str) -> ParserContext:
    settings = get_settings()
    timezone = (
        settings.auth_default_timezone
        if parser_name == "auth_log"
        else settings.default_timezone
    )
    return ParserContext(
        case_id=evidence.case_id,
        evidence_id=evidence.id,
        source_filename=evidence.original_filename,
        reference_date=evidence.uploaded_at or datetime.now(timezone.utc),
        default_year=settings.auth_default_year,
        timezone=timezone,
    )


def _delete_derived_data(db: Session, evidence: Evidence) -> None:
    reconciliation_service.clear_findings(db, evidence.case_id)

    rule_finding_ids = list(
        db.scalars(
            select(FindingEvidence.finding_id)
            .join(Finding, Finding.id == FindingEvidence.finding_id)
            .where(
                FindingEvidence.evidence_id == evidence.id,
                Finding.detection_method == "deterministic_rule",
            )
        )
    )
    if rule_finding_ids:
        db.execute(
            delete(FindingEvidence).where(
                FindingEvidence.finding_id.in_(rule_finding_ids)
            )
        )
        db.execute(delete(Finding).where(Finding.id.in_(rule_finding_ids)))
    db.execute(delete(Event).where(Event.evidence_id == evidence.id))
    db.flush()


def _persist_events(
    db: Session, evidence: Evidence, result: ParseResult
) -> tuple[list[Event], dict[str, Event]]:
    created: list[Event] = []
    by_locator: dict[str, Event] = {}
    for draft in result.events:
        event = Event(
            case_id=evidence.case_id,
            evidence_id=evidence.id,
            event_type=draft.event_type,
            timestamp_raw=draft.timestamp_raw,
            timestamp_normalized=draft.timestamp_normalized,
            timestamp_confidence=draft.timestamp_confidence,
            timestamp_timezone=draft.timestamp_timezone,
            source_filename=evidence.original_filename,
            source_locator=draft.source_locator,
            source_snippet=draft.source_snippet,
            attributes_json=draft.attributes,
            warnings_json=draft.warnings,
            parser_name=result.parser_name,
            parser_version=result.parser_version,
        )
        db.add(event)
        db.flush()
        created.append(event)
        by_locator[draft.source_locator] = event

        seen: set[tuple[str, str, str]] = set()
        for entity_draft in draft.entities:
            if not entity_draft.value:
                continue
            key = (entity_draft.entity_type, entity_draft.value, entity_draft.role)
            if key in seen:
                continue
            seen.add(key)
            entity = entity_service.get_or_create_entity(
                db,
                evidence.case_id,
                entity_draft.entity_type,
                entity_draft.value,
                role=entity_draft.role,
            )
            entity_service.link_event_entity(
                db,
                event,
                entity,
                role=entity_draft.role,
                raw_value=entity_draft.raw_value or entity_draft.value,
            )
    return created, by_locator


def _severity_for_level(level: str | None) -> str:
    if level == "HIGH SUSPICION":
        return "high"
    if level == "SUSPICIOUS":
        return "medium"
    return "low"


def _persist_auth_alerts(
    db: Session,
    evidence: Evidence,
    result: ParseResult,
    events_by_locator: dict[str, Event],
) -> list[Finding]:
    created: list[Finding] = []
    for alert in result.metadata.get("alerts", []) or []:
        level = alert.get("level")
        source_ip = alert.get("source_ip")
        rule_ids = alert.get("rule_ids", [])
        reasons = alert.get("reasons", [])
        limitations = alert.get("limitations", [])
        finding = Finding(
            case_id=evidence.case_id,
            severity=_severity_for_level(level),
            category="authentication",
            title=(
                f"Authentication indicator: {str(level or 'suspicious').lower()} "
                f"for {source_ip or 'unknown source'}"
            ),
            explanation=(
                ("Rules: " + ", ".join(rule_ids) + ". " if rule_ids else "")
                + "; ".join(reasons)
            ),
            detection_method="deterministic_rule",
            confidence="medium",
            status="open",
            limitations=" ".join(limitations),
            alternative_explanations=(
                "Failed logins can result from user error, stale credentials, "
                "automated scanners, shared NAT egress, or authorized testing. "
                "A successful login after failures may be legitimate."
            ),
        )
        db.add(finding)
        db.flush()
        created.append(finding)

        db.add(
            FindingEvidence(
                finding_id=finding.id,
                evidence_id=evidence.id,
                event_id=None,
                role="supporting_evidence",
                source_locator="auth_log",
            )
        )
        for line_number in alert.get("event_line_numbers", []):
            event = events_by_locator.get(f"line:{line_number}")
            if event is None:
                continue
            db.add(
                FindingEvidence(
                    finding_id=finding.id,
                    evidence_id=evidence.id,
                    event_id=event.id,
                    role="supporting_event",
                    source_locator=event.source_locator,
                )
            )
    db.flush()
    return created


def _status_for(result: ParseResult, events: list[Event]) -> tuple[str, str | None]:
    if result.parser_name == "image" and result.metadata.get("ocr_available") is False:
        return (
            "ocr_unavailable",
            "OCR text could not be extracted. Install Tesseract or verify the image.",
        )
    if events:
        return "parsed", None
    if result.warnings:
        return (
            "partially_parsed",
            "The parser recognized the file format but produced no canonical events.",
        )
    return "failed", "No supported records were parsed from this file."


def parse_evidence(
    db: Session,
    evidence: Evidence,
    *,
    parser_hint: str | None = None,
    reparse: bool = False,
) -> dict[str, Any]:
    with evidence_service.materialize_evidence(evidence) as path:
        parser = detect_parser(path, evidence.original_filename, parser_hint)
        if parser is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No parser is available for this file. Supported: {SUPPORTED_DESCRIPTION}",
            )

        if evidence.processing_status == "parsed" and not reparse:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Evidence has already been parsed. Use reparse=true to parse it again.",
            )

        if reparse:
            _delete_derived_data(db, evidence)

        evidence.processing_status = "parsing"
        evidence.processing_error = None
        db.flush()

        try:
            result = parser.parse(path, _parser_context(evidence, parser.name))
        except HTTPException:
            raise
        except Exception as error:  # noqa: BLE001 - surface parser failures to the caller
            evidence.processing_status = "failed"
            evidence.processing_error = str(error)
            audit_service.record(
                db,
                evidence.case_id,
                "evidence.parse_failed",
                evidence_id=evidence.id,
                details={"parser": parser.name, "error": str(error)},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Parsing failed: {error}",
            ) from error

    events, events_by_locator = _persist_events(db, evidence, result)
    auth_findings = _persist_auth_alerts(db, evidence, result, events_by_locator)
    reconciliation_findings = reconciliation_service.run(db, evidence.case_id)

    processing_status, processing_error = _status_for(result, events)
    evidence.parser_name = result.parser_name
    evidence.parser_version = result.parser_version
    evidence.processing_status = processing_status
    evidence.processing_error = processing_error
    evidence.metadata_json = {
        **result.metadata,
        "warnings": [warning.message for warning in result.warnings[:50]],
        "events_created": len(events),
        "findings_created": len(auth_findings) + len(reconciliation_findings),
    }

    audit_service.record(
        db,
        evidence.case_id,
        "evidence.parsed",
        evidence_id=evidence.id,
        details={
            "parser": result.parser_name,
            "parser_version": result.parser_version,
            "events_created": len(events),
            "auth_findings": len(auth_findings),
            "reconciliation_findings": len(reconciliation_findings),
            "status": processing_status,
        },
    )
    db.commit()
    db.refresh(evidence)

    return {
        "evidence_id": evidence.id,
        "parser_name": result.parser_name,
        "parser_version": result.parser_version,
        "events_created": len(events),
        "findings_created": len(auth_findings) + len(reconciliation_findings),
        "warnings": [warning.message for warning in result.warnings[:50]],
        "summary": {
            "parser_metadata": result.metadata,
            "events_created": len(events),
            "auth_findings": len(auth_findings),
            "reconciliation_findings": len(reconciliation_findings),
        },
        "status": processing_status,
    }
