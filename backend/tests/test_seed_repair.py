from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.models import Case
from app.services import demo_seed_service, evidence_service


def test_partial_demo_is_repaired_without_duplicate_evidence(db, case):
    sample = Path(get_settings().sample_data_dir) / "operation_digital_trail" / "auth.log"
    assert sample.is_file()
    case_model = db.get(Case, case["id"])
    assert case_model is not None
    first = evidence_service.create_evidence(
        db, case_model, demo_seed_service._as_upload(sample)
    )
    assert first.processing_status == "uploaded"

    errors: list[dict[str, str]] = []
    repaired = demo_seed_service._repair_demo_case(
        db, case_model, [sample], errors
    )
    assert repaired is True
    db.refresh(first)
    assert first.processing_status == "parsed"
    assert case_model.is_demo is True
    assert errors == []
