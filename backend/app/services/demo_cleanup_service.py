from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Case
from . import case_service

logger = logging.getLogger("uvicorn.error")


def _delete_demo_case(db: Session, case: Case) -> None:
    case_service.delete_case(db, case)


def cleanup_expired_demo_copies(db: Session, older_than_hours: int | None = None) -> int:
    """Remove abandoned visitor-owned demo cases and their stored objects.

    The shared demo templates have no owner and are never removed. Only old
    visitor copies created by the former per-visitor demo implementation match.
    """
    settings = get_settings()
    ttl = settings.demo_copy_ttl_hours if older_than_hours is None else older_than_hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, ttl))
    cases = list(
        db.scalars(
            select(Case).where(
                Case.is_demo.is_(True),
                Case.owner_id.is_not(None),
                Case.created_at < cutoff,
            )
        )
    )
    for case in cases:
        _delete_demo_case(db, case)
    if cases:
        logger.info("Removed %s abandoned demo visitor copies.", len(cases))
    return len(cases)
