from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import Settings
from ..models import Entity, Event, EventEntity, Finding, Relationship, Report
from ..schemas.ai import AiSuggestionRead, AiSuggestionsResponse

DEFAULT_SUGGESTIONS: list[AiSuggestionRead] = [
    AiSuggestionRead(
        question="Summarize this case.",
        reason="Start with an overview of what the evidence shows.",
    ),
    AiSuggestionRead(
        question="What happened first?",
        reason="Establish the earliest recorded activity.",
    ),
    AiSuggestionRead(
        question="What information is still missing?",
        reason="Identify gaps before drawing conclusions.",
    ),
]


def build_suggestions(
    db: Session,
    case_id: str,
    settings: Settings | None = None,
) -> AiSuggestionsResponse:
    """Derive copilot suggestions from the case's stored records.

    The list is ordered by what the investigator has not done yet, so an empty
    case still receives useful starting questions.
    """

    items: list[AiSuggestionRead] = []

    findings = list(db.scalars(select(Finding).where(Finding.case_id == case_id)))
    unreviewed_high = [
        finding
        for finding in findings
        if finding.severity in ("high", "critical") and finding.status in ("open", "needs_review")
    ]
    if unreviewed_high:
        first = unreviewed_high[0]
        items.append(
            AiSuggestionRead(
                question=f"Explain the finding \"{first.title}\" and cite the records behind it.",
                reason="A high-severity finding is still unreviewed.",
            )
        )

    shared_entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.case_id == case_id)
            .options(selectinload(Entity.event_links).selectinload(EventEntity.event))
        )
    )
    multi_source = [
        entity
        for entity in shared_entities
        if len({link.event.evidence_id for link in entity.event_links if link.event}) > 1
    ]
    if multi_source:
        entity = sorted(multi_source, key=lambda item: item.event_count, reverse=True)[0]
        items.append(
            AiSuggestionRead(
                question=(
                    f"Which sources mention {entity.value_original}, and what do they record?"
                ),
                reason="This entity appears in more than one evidence file.",
            )
        )

    auth_events = list(
        db.scalars(
            select(Event)
            .where(
                Event.case_id == case_id,
                Event.event_type.startswith("auth"),
            )
            .limit(50)
        )
    )
    if auth_events:
        items.append(
            AiSuggestionRead(
                question="Show the authentication activity and any failed sign-in sequences.",
                reason=f"{len(auth_events)} authentication events are stored for this case.",
            )
        )

    relationships = list(
        db.scalars(
            select(Relationship)
            .where(
                Relationship.case_id == case_id,
                Relationship.review_status == "unreviewed",
            )
            .limit(50)
        )
    )
    if relationships:
        items.append(
            AiSuggestionRead(
                question="Explain the unreviewed relationships and the evidence supporting them.",
                reason=f"{len(relationships)} relationships have no analyst decision yet.",
            )
        )

    if not items:
        items.extend(DEFAULT_SUGGESTIONS)
    elif len(items) < 4:
        items.append(
            AiSuggestionRead(
                question="Summarize this case.",
                reason="A short overview is often the fastest way to orient yourself.",
            )
        )

    return AiSuggestionsResponse(
        items=items[:6],
        generated_at=datetime.now(timezone.utc),
    )
