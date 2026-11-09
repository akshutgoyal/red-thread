from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Case, Evidence, Report
from app.services import case_service, storage_service
from app.services.demo_cleanup_service import cleanup_expired_demo_copies
from app.schemas.case import CaseCreate


def test_cleanup_removes_old_demo_copies_and_storage(db):
    template = case_service.create_case(
        db,
        CaseCreate(title="Demo Template Keep", description="template"),
        is_demo=True,
    )
    abandoned = case_service.create_case(
        db,
        CaseCreate(title="Old Demo Copy", description="old"),
        owner_id="demo-old-visitor",
        is_demo=True,
    )
    abandoned.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    evidence_key = storage_service.evidence_key(abandoned.id, "old.txt")
    report_key = storage_service.report_key(abandoned.id, "old.pdf")
    storage_service.save_bytes(evidence_key, b"old evidence", content_type="text/plain")
    storage_service.save_bytes(report_key, b"old report", content_type="application/pdf")
    db.add(Evidence(
        case_id=abandoned.id,
        original_filename="old.txt",
        stored_filename="old.txt",
        relative_path=evidence_key,
        media_type="text/plain",
        size_bytes=12,
        sha256="0" * 64,
        processing_status="uploaded",
    ))
    db.add(Report(
        case_id=abandoned.id,
        report_type="pdf",
        filename="old.pdf",
        relative_path=report_key,
        status="ready",
    ))
    db.commit()

    removed = cleanup_expired_demo_copies(db, older_than_hours=1)
    assert removed == 1
    assert db.get(Case, abandoned.id) is None
    assert db.get(Case, template.id) is not None
    assert not storage_service.exists(evidence_key)
    assert not storage_service.exists(report_key)
