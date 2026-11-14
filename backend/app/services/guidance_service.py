from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    AiQuery,
    Case,
    Entity,
    Event,
    Evidence,
    Finding,
    Relationship,
    Report,
    ReviewDecision,
)
from ..schemas.guidance import (
    GuidanceAction,
    GuidanceAttention,
    GuidanceResponse,
    GuidanceStage,
    GuidanceSummary,
)
from . import ai_service
from .count_service import case_counts

SETTLED_EVIDENCE_STATUSES = {"parsed", "partially_parsed", "ocr_unavailable"}
ATTENTION_EVIDENCE_STATUSES = {"uploaded", "parsing", "failed"}
HIGH_SEVERITIES = ("high", "critical")
REVIEWED_FINDING_STATUSES = ("accepted", "rejected", "needs_more_evidence")
EVENT_REVIEW_DECISIONS = ("relevant", "not_relevant", "needs_review")


def _count(db: Session, model, *conditions) -> int:
    return int(db.scalar(select(func.count(model.id)).where(*conditions)) or 0)


def _case_path(case_id: str, suffix: str = "") -> str:
    base = f"/cases/{case_id}"
    return f"{base}/{suffix}" if suffix else base


def _parse_warning_count(evidence: Evidence) -> int:
    metadata = evidence.metadata_json or {}
    warnings = metadata.get("warnings")
    if isinstance(warnings, list):
        return len(warnings)
    return 0


def _latest_event_reviews(db: Session, case_id: str) -> dict[str, str]:
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


def build_guidance(
    db: Session,
    case_id: str,
    settings: Settings | None = None,
) -> GuidanceResponse:
    """Derive investigation guidance from stored records only.

    Every stage status and recommendation in this response is a pure function
    of persisted rows. Nothing is hardcoded to a particular demo case.
    """

    case = db.get(Case, case_id)
    if case is None:
        raise ValueError("Case not found.")

    evidence_rows = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id)))
    evidence_count = len(evidence_rows)
    settled = [item for item in evidence_rows if item.processing_status in SETTLED_EVIDENCE_STATUSES]
    needs_attention_rows = [
        item for item in evidence_rows if item.processing_status in ATTENTION_EVIDENCE_STATUSES
    ]
    warning_rows = [item for item in evidence_rows if _parse_warning_count(item) > 0]
    unverified_rows = [item for item in evidence_rows if not item.hash_verified]

    event_count = _count(db, Event, Event.case_id == case_id)
    dated_event_count = _count(
        db,
        Event,
        Event.case_id == case_id,
        Event.timestamp_normalized.is_not(None),
    )
    entity_count = _count(db, Entity, Entity.case_id == case_id)

    finding_rows = list(db.scalars(select(Finding).where(Finding.case_id == case_id)))
    open_findings = [item for item in finding_rows if item.status in ("open", "needs_review")]
    high_findings = [item for item in finding_rows if item.severity in HIGH_SEVERITIES]
    unreviewed_high = [item for item in high_findings if item.status not in REVIEWED_FINDING_STATUSES]

    relationship_rows = list(
        db.scalars(select(Relationship).where(Relationship.case_id == case_id))
    )
    unreviewed_relationships = [
        item for item in relationship_rows if item.review_status == "unreviewed"
    ]
    # Canonical counts, shared with the relationship graph and the dashboard.
    stored = case_counts(db, case_id)

    event_reviews = _latest_event_reviews(db, case_id)
    reviewed_event_count = sum(
        1 for decision in event_reviews.values() if decision in EVENT_REVIEW_DECISIONS
    )

    ai_query_count = _count(db, AiQuery, AiQuery.case_id == case_id)
    validated_ai_count = _count(
        db,
        AiQuery,
        AiQuery.case_id == case_id,
        AiQuery.validation_status.in_(("validated", "partially_validated")),
    )
    report_count = _count(db, Report, Report.case_id == case_id)

    ai_configured = False
    ai_reason = ""
    if settings is not None:
        status = ai_service.resolve_provider(settings)
        ai_configured = status.configured
        ai_reason = status.reason

    # ---------------------------------------------------------------- stages
    upload_complete = evidence_count > 0
    integrity_complete = evidence_count > 0 and not unverified_rows
    processing_complete = evidence_count > 0 and not needs_attention_rows
    events_reviewed = event_count > 0 and (
        reviewed_event_count >= event_count or event_count == 0
    )
    timeline_complete = dated_event_count > 0
    relationships_complete = len(relationship_rows) > 0
    suspicious_complete = len(high_findings) > 0 and not unreviewed_high
    ai_complete = validated_ai_count > 0
    report_complete = report_count > 0

    def status(complete: bool, started: bool) -> str:
        if complete:
            return "complete"
        return "in_progress" if started else "not_started"

    stages = [
        GuidanceStage(
            key="create_case",
            index=1,
            title="Create case",
            description="A case groups all evidence, events and findings for one investigation.",
            what_to_do="Name the investigation and record what you are looking into.",
            output="An empty case ready for evidence.",
            status="complete",
            href=_case_path(case_id),
            completed_count=1,
            total_count=1,
        ),
        GuidanceStage(
            key="upload_evidence",
            index=2,
            title="Upload evidence",
            description=(
                "Evidence files are stored unchanged and hashed so their integrity can "
                "be verified later."
            ),
            what_to_do="Upload the files you were given: logs, exports, images or location data.",
            output="Stored files with a SHA-256 digest and an audit record.",
            status=status(upload_complete, upload_complete),
            href=_case_path(case_id, "evidence/intake"),
            completed_count=evidence_count,
            total_count=max(evidence_count, 1),
        ),
        GuidanceStage(
            key="verify_integrity",
            index=3,
            title="Verify evidence integrity",
            description=(
                "Re-hashing a stored file proves it still matches the digest recorded "
                "at intake, so you can show it has not changed since."
            ),
            what_to_do="Open each file in the vault and run Verify integrity.",
            output="A recorded verification for every file you can rely on.",
            status=status(integrity_complete, evidence_count > 0),
            href=_case_path(case_id, "evidence"),
            completed_count=evidence_count - len(unverified_rows),
            total_count=evidence_count,
        ),
        GuidanceStage(
            key="validate_process",
            index=4,
            title="Validate and process",
            description=(
                "Each file is parsed into structured events. Warnings tell you what "
                "could not be read."
            ),
            what_to_do="Parse every file and review the files that need attention.",
            output="Extracted events and any parser warnings.",
            status=status(processing_complete, evidence_count > 0),
            href=_case_path(case_id, "evidence"),
            completed_count=len(settled),
            total_count=evidence_count,
        ),
        GuidanceStage(
            key="extract_entities",
            index=5,
            title="Extracted entities",
            description=(
                "Phone numbers, devices, accounts and people are pulled out of the "
                "records so the same identifier can be followed across sources."
            ),
            what_to_do="Open the entity explorer and check that the extracted identifiers are the ones you expected.",
            output="An entity register with a source reference behind each mention.",
            status=status(entity_count > 0, entity_count > 0),
            href=_case_path(case_id, "entities"),
            completed_count=entity_count,
            total_count=max(entity_count, 1),
        ),
        GuidanceStage(
            key="review_events",
            index=6,
            title="Review extracted events",
            description=(
                "Confirm which extracted events matter to the investigation before "
                "you rely on them."
            ),
            what_to_do="Open each event, check the original record, and mark it relevant or not relevant.",
            output="A reviewed event set with an audit trail.",
            status=status(events_reviewed, event_count > 0),
            href=_case_path(case_id, "events"),
            completed_count=reviewed_event_count,
            total_count=event_count,
        ),
        GuidanceStage(
            key="explore_timeline",
            index=7,
            title="Explore the timeline",
            description="The timeline places every dated event in order across all sources.",
            what_to_do="Look for sequences, gaps and events that occur close together.",
            output="An ordered view of the case and its correlated groups.",
            status=status(timeline_complete, dated_event_count > 0),
            href=_case_path(case_id, "timeline"),
            completed_count=dated_event_count,
            total_count=event_count,
        ),
        GuidanceStage(
            key="understand_relationships",
            index=8,
            title="Understand relationships",
            description=(
                "Relationships show which entities appear together and which evidence "
                "supports the connection."
            ),
            what_to_do="Open a relationship and read its supporting records before drawing conclusions.",
            output="Reviewed correlations with provenance.",
            status=status(
                relationships_complete and not unreviewed_relationships,
                relationships_complete,
            ),
            href=_case_path(case_id, "graph"),
            completed_count=stored.total_relationships - stored.unreviewed_relationships,
            total_count=stored.total_relationships,
        ),
        GuidanceStage(
            key="investigate_patterns",
            index=9,
            title="Investigate suspicious patterns",
            description=(
                "High-severity findings mark activity that deserves a closer look. "
                "They are leads, not conclusions."
            ),
            what_to_do="Review every high or critical finding and record an analyst decision.",
            output="Accepted, rejected or needs-more-evidence decisions.",
            status=status(suspicious_complete, len(high_findings) > 0),
            href=_case_path(case_id, "findings"),
            completed_count=len(high_findings) - len(unreviewed_high),
            total_count=len(high_findings),
        ),
        GuidanceStage(
            key="ai_analysis",
            index=10,
            title="AI-assisted analysis",
            description=(
                "The copilot answers questions using only the records in this case and "
                "cites what it used."
            ),
            what_to_do="Ask a focused question and verify the cited records yourself.",
            output="A grounded answer with citations and stated uncertainties.",
            status=status(ai_complete, ai_query_count > 0),
            href=_case_path(case_id, "ai"),
            completed_count=validated_ai_count,
            total_count=max(ai_query_count, 1),
        ),
        GuidanceStage(
            key="generate_report",
            index=11,
            title="Generate the investigation report",
            description=(
                "The report collects the evidence inventory, timeline, findings and "
                "limitations into one document."
            ),
            what_to_do="Generate the report and review it before sharing.",
            output="A draft PDF and JSON report for human review.",
            status=status(report_complete, report_complete),
            href=_case_path(case_id, "reports"),
            completed_count=report_count,
            total_count=max(report_count, 1),
        ),
    ]

    # ----------------------------------------------------------- next action
    next_action = _next_action(
        case_id=case_id,
        evidence_count=evidence_count,
        unparsed=needs_attention_rows,
        warning_rows=warning_rows,
        event_count=event_count,
        unreviewed_high=unreviewed_high,
        unreviewed_relationships=unreviewed_relationships,
        ai_configured=ai_configured,
        report_count=report_count,
    )

    attention: list[GuidanceAttention] = []
    if needs_attention_rows:
        attention.append(
            GuidanceAttention(
                kind="unparsed_evidence",
                title="Files still need processing",
                detail=(
                    f"{len(needs_attention_rows)} of {evidence_count} files have not finished "
                    "processing successfully."
                ),
                href=_case_path(case_id, "evidence"),
                count=len(needs_attention_rows),
            )
        )
    if warning_rows:
        attention.append(
            GuidanceAttention(
                kind="parse_warnings",
                title="Parsed with warnings",
                detail=(
                    f"{len(warning_rows)} files parsed with warnings. Check what was "
                    "not extracted before relying on their events."
                ),
                href=_case_path(case_id, "evidence"),
                count=len(warning_rows),
            )
        )
    if unverified_rows:
        attention.append(
            GuidanceAttention(
                kind="integrity_unverified",
                title="Integrity not yet verified",
                detail=(
                    f"{len(unverified_rows)} files have not been re-hashed since upload."
                ),
                href=_case_path(case_id, "evidence"),
                count=len(unverified_rows),
            )
        )
    if unreviewed_high:
        attention.append(
            GuidanceAttention(
                kind="open_high_findings",
                title="High-severity findings awaiting review",
                detail=f"{len(unreviewed_high)} high or critical findings have no decision yet.",
                href=_case_path(case_id, "findings"),
                count=len(unreviewed_high),
            )
        )
    if unreviewed_relationships:
        attention.append(
            GuidanceAttention(
                kind="unreviewed_relationships",
                title="Relationships awaiting review",
                detail=(
                    f"{len(unreviewed_relationships)} generated relationships are unreviewed. "
                    "Correlations are leads, not proof."
                ),
                href=_case_path(case_id, "workspace"),
                count=len(unreviewed_relationships),
            )
        )
    if settings is not None and not ai_configured:
        attention.append(
            GuidanceAttention(
                kind="ai_unconfigured",
                title="AI assistant is not configured",
                detail=ai_reason or "Set an AI provider and API key to enable the copilot.",
                href=_case_path(case_id, "ai"),
                count=0,
            )
        )
    if evidence_count > 0 and event_count == 0:
        attention.append(
            GuidanceAttention(
                kind="no_events",
                title="No events extracted",
                detail=(
                    "Evidence is stored but no events were extracted. Check the parser "
                    "status and the file format."
                ),
                href=_case_path(case_id, "evidence"),
                count=0,
            )
        )
    if report_count == 0 and evidence_count > 0:
        attention.append(
            GuidanceAttention(
                kind="no_reports",
                title="No report generated",
                detail="Generate a draft report once your review is complete.",
                href=_case_path(case_id, "reports"),
                count=0,
            )
        )

    for position, stage in enumerate(stages):
        if stage.next_step:
            continue
        following = stages[position + 1] if position + 1 < len(stages) else None
        stage.next_step = (
            f"Next stage: {following.title}. {following.description}"
            if following is not None
            else "Generate and review the draft report, then record your conclusions."
        )

    return GuidanceResponse(
        case_id=case_id,
        generated_at=datetime.now(timezone.utc),
        stages=stages,
        next_action=next_action,
        attention=attention,
        summary=GuidanceSummary(
            evidence=evidence_count,
            parsed=len(settled),
            needs_attention=len(needs_attention_rows),
            events=event_count,
            entities=entity_count,
            open_findings=len(open_findings),
            unreviewed_relationships=len(unreviewed_relationships),
            reports=report_count,
            total_relationships=stored.total_relationships,
            documented_relationships=stored.documented_relationships,
            inferred_leads=stored.inferred_leads,
            unique_connections=stored.unique_connections,
            raw_edges=stored.raw_edges,
            structural_edges=stored.containment_edges,
        ),
        scanned_events=event_count,
    )


def _next_action(
    *,
    case_id: str,
    evidence_count: int,
    unparsed: list[Evidence],
    warning_rows: list[Evidence],
    event_count: int,
    unreviewed_high: list[Finding],
    unreviewed_relationships: list[Relationship],
    ai_configured: bool,
    report_count: int,
) -> GuidanceAction:
    if evidence_count == 0:
        return GuidanceAction(
            id="upload_evidence",
            title="Upload evidence files to begin your investigation",
            reason=(
                "This case has no evidence yet. Nothing can be extracted or reviewed "
                "until at least one file is uploaded."
            ),
            action_label="Upload evidence",
            href=_case_path(case_id, "evidence/intake"),
        )
    if unparsed:
        return GuidanceAction(
            id="finish_processing",
            title=f"{len(unparsed)} files still need processing",
            reason=(
                "Files that have not been parsed produce no events, so they are "
                "missing from the timeline and graph."
            ),
            action_label="Review processing status",
            href=_case_path(case_id, "evidence"),
            tone="warning",
        )
    if warning_rows:
        return GuidanceAction(
            id="review_warnings",
            title=f"{len(warning_rows)} files parsed with warnings",
            reason=(
                "Warnings mark values that could not be read. Review them before "
                "relying on those events."
            ),
            action_label="Review warnings",
            href=_case_path(case_id, "evidence"),
            tone="warning",
        )
    if event_count == 0:
        return GuidanceAction(
            id="no_events",
            title="Evidence processed but no events were extracted",
            reason=(
                "The parser recognized the file but produced no canonical events. "
                "Check the file format and parser mapping."
            ),
            action_label="Open evidence vault",
            href=_case_path(case_id, "evidence"),
            tone="warning",
        )
    if unreviewed_high:
        return GuidanceAction(
            id="review_findings",
            title=f"{len(unreviewed_high)} high-severity findings await review",
            reason=(
                "High-severity findings are investigative leads. Each needs a human "
                "decision before it appears in a report as reviewed."
            ),
            action_label="Review findings",
            href=_case_path(case_id, "findings"),
            tone="critical",
        )
    if unreviewed_relationships:
        return GuidanceAction(
            id="review_relationships",
            title=f"{len(unreviewed_relationships)} relationships have not been reviewed",
            reason=(
                "Correlations are generated from stored records. Reviewing them "
                "confirms or rejects each proposed connection."
            ),
            action_label="Open workspace",
            href=_case_path(case_id, "workspace"),
            tone="info",
        )
    if ai_configured:
        return GuidanceAction(
            id="ask_copilot",
            title="Ask the copilot to summarise this case",
            reason=(
                "The assistant answers from this case's records and cites every "
                "reference it uses."
            ),
            action_label="Open AI assistant",
            href=_case_path(case_id, "ai"),
        )
    if report_count == 0:
        return GuidanceAction(
            id="generate_report",
            title="Generate the investigation report",
            reason=(
                "The report collects the evidence inventory, timeline, findings and "
                "limitations into one document for human review."
            ),
            action_label="Open reports",
            href=_case_path(case_id, "reports"),
        )
    return GuidanceAction(
        id="final_review",
        title="Case is ready for final review",
        reason=(
            "Evidence is processed, findings and relationships are reviewed, and a "
            "report exists. Confirm the narrative before sharing."
        ),
        action_label="Open workspace",
        href=_case_path(case_id, "workspace"),
    )
