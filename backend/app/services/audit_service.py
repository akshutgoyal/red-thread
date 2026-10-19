from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent


def record(
    db: Session,
    case_id: str,
    action: str,
    *,
    evidence_id: str | None = None,
    actor: str = "investigator",
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        actor=actor,
        action=action,
        details_json=details or {},
    )
    db.add(event)
    db.flush()
    return event
