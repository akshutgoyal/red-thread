from __future__ import annotations

import logging
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

from ..config import Settings
from ..models import Case, Event, Evidence, Finding
from ..schemas.case import CaseCreate
from . import audit_service, case_service, evidence_service, investigation_service

logger = logging.getLogger("uvicorn.error")

DEMO_CASES: list[dict[str, str]] = [
    {
        "title": "Benign Control (Synthetic Demo)",
        "directory": "benign_control",
        "description": (
            "Synthetic benign control with a matching invoice and UPI statement. "
            "Reconciliation should validate the arithmetic without a high-severity anomaly."
        ),
    },
    {
        "title": "Operation PhishTrace (Synthetic Demo)",
        "directory": "operation_phishtrace",
        "description": (
            "Synthetic Operation PhishTrace demonstration. All files are generated "
            "test data and are not real evidence."
        ),
    },
]

EVIDENCE_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".txt",
    ".log",
    ".pdf",
    ".eml",
    ".png",
    ".jpg",
    ".jpeg",
}
SKIP_NAMES = {"readme.md", "manifest.json"}


def _sample_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in EVIDENCE_SUFFIXES
        and path.name.lower() not in SKIP_NAMES
    )


def _as_upload(path: Path) -> UploadFile:
    data = path.read_bytes()
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return UploadFile(
        file=BytesIO(data),
        filename=path.name,
        headers=Headers({"content-type": media_type}),
    )


def _case_counts(db: Session, case_id: str) -> dict[str, int]:
    return {
        "evidence": db.scalar(
            select(func.count(Evidence.id)).where(Evidence.case_id == case_id)
        )
        or 0,
        "events": db.scalar(
            select(func.count(Event.id)).where(Event.case_id == case_id)
        )
        or 0,
        "findings": db.scalar(
            select(func.count(Finding.id)).where(Finding.case_id == case_id)
        )
        or 0,
    }


def seed_demo_if_needed(db: Session, settings: Settings) -> dict[str, Any]:
    sample_root = settings.sample_data_dir
    if not sample_root.is_dir():
        return {
            "seeded": False,
            "reason": f"Sample data directory not found: {sample_root}",
            "cases": [],
            "errors": [],
        }

    created: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for spec in DEMO_CASES:
        title = spec["title"]
        existing = db.scalar(select(Case).where(Case.title == title))
        if existing is not None:
            logger.info("Demo seed: case already exists: %s", title)
            continue

        case = case_service.create_case(
            db,
            CaseCreate(title=title, description=spec["description"]),
        )
        audit_service.record(
            db,
            case.id,
            "case.created",
            details={"source": "demo_seed", "title": case.title},
        )
        db.commit()
        logger.info("Demo seed: created case %s (%s)", case.id, case.title)

        files = _sample_files(sample_root / spec["directory"])
        if not files:
            errors.append(
                {
                    "file": spec["directory"],
                    "error": "No supported sample evidence files found.",
                }
            )
            continue

        for path in files:
            try:
                evidence = evidence_service.create_evidence(db, case, _as_upload(path))
                result = investigation_service.parse_evidence(db, evidence)
                logger.info(
                    "Demo seed: %s -> parser=%s events=%s findings=%s status=%s",
                    path.name,
                    result["parser_name"],
                    result["events_created"],
                    result["findings_created"],
                    result["status"],
                )
            except Exception as error:  # noqa: BLE001 - seed must report partial failures
                logger.exception("Demo seed: failed to process %s", path.name)
                errors.append({"file": path.name, "error": str(error)})

        db.refresh(case)
        counts = _case_counts(db, case.id)
        created.append(
            {
                "id": case.id,
                "title": case.title,
                "evidence_count": counts["evidence"],
                "event_count": counts["events"],
                "finding_count": counts["findings"],
            }
        )

    return {
        "seeded": bool(created),
        "cases": created,
        "errors": errors,
    }
