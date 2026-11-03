from __future__ import annotations

import mimetypes
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Case, Evidence
from ..models.base import new_id, utcnow
from . import audit_service, hashing_service, storage_service

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".pdf": "application/pdf",
    ".eml": "message/rfc822",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def sanitize_filename(filename: str | None) -> str:
    name = Path(filename or "evidence").name.strip().replace("\x00", "")
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    return name[:512]


def media_type_for(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or ALLOWED_EXTENSIONS.get(extension) or "application/octet-stream"


def validate_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{extension or '(none)'}'. Supported: {supported}",
        )
    return extension


def create_evidence(db: Session, case: Case, upload: UploadFile) -> Evidence:
    settings = get_settings()
    original_filename = sanitize_filename(upload.filename)
    extension = validate_extension(original_filename)

    evidence_id = new_id()
    stored_filename = f"{evidence_id}{extension}"
    relative_path = storage_service.evidence_key(case.id, stored_filename)
    media_type = media_type_for(original_filename)

    try:
        size, sha256 = storage_service.save_stream(
            relative_path,
            upload.file,
            max_bytes=settings.max_upload_bytes,
            content_type=media_type,
        )
    except storage_service.StorageLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        ) from error
    except storage_service.StorageEmptyFile as error:
        raise HTTPException(
            status_code=422, detail="Empty files are not accepted."
        ) from error
    finally:
        upload.file.close()

    evidence = Evidence(
        id=evidence_id,
        case_id=case.id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        relative_path=relative_path,
        media_type=media_type,
        size_bytes=size,
        sha256=sha256,
        uploaded_at=utcnow(),
        processing_status="uploaded",
    )
    db.add(evidence)
    audit_service.record(
        db,
        case.id,
        "evidence.uploaded",
        evidence_id=evidence.id,
        details={
            "filename": original_filename,
            "size_bytes": size,
            "sha256": evidence.sha256,
            "media_type": evidence.media_type,
        },
    )
    db.commit()
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, case_id: str) -> list[Evidence]:
    return list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(Evidence.uploaded_at.desc())
        )
    )


def get_evidence(db: Session, evidence_id: str, case_id: str) -> Evidence | None:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or evidence.case_id != case_id:
        return None
    return evidence


def get_evidence_path(evidence: Evidence) -> Path:
    settings = get_settings()
    if settings.is_r2:
        raise HTTPException(
            status_code=500,
            detail="Evidence is stored in object storage; use materialize_evidence().",
        )
    root = settings.evidence_dir.resolve()
    path = (settings.resolved_data_dir / evidence.relative_path).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=404, detail="Evidence file is outside the evidence vault.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file is missing from the vault.")
    return path


@contextmanager
def materialize_evidence(evidence: Evidence) -> Iterator[Path]:
    try:
        with storage_service.materialize(evidence.relative_path) as path:
            yield path
    except storage_service.StorageObjectNotFound as error:
        raise HTTPException(
            status_code=404, detail="Evidence file is missing from the vault."
        ) from error


def verify_evidence(db: Session, evidence: Evidence) -> dict:
    with materialize_evidence(evidence) as path:
        actual = hashing_service.sha256_file(path)
    verified = actual == evidence.sha256
    evidence.hash_verified = verified
    evidence.hash_verified_at = utcnow()
    audit_service.record(
        db,
        evidence.case_id,
        "evidence.verified" if verified else "evidence.verification_failed",
        evidence_id=evidence.id,
        details={
            "expected_sha256": evidence.sha256,
            "actual_sha256": actual,
            "verified": verified,
        },
    )
    db.commit()
    db.refresh(evidence)
    return {
        "evidence_id": evidence.id,
        "expected_sha256": evidence.sha256,
        "actual_sha256": actual,
        "verified": verified,
        "checked_at": evidence.hash_verified_at,
        "message": (
            "Stored file matches the recorded SHA-256 digest."
            if verified
            else "Stored file does NOT match the recorded digest. It may have been altered."
        ),
    }


def read_text_preview(evidence: Evidence, max_bytes: int = 200_000) -> dict:
    try:
        data = storage_service.read_prefix(evidence.relative_path, max_bytes + 1)
    except storage_service.StorageObjectNotFound as error:
        raise HTTPException(
            status_code=404, detail="Evidence file is missing from the vault."
        ) from error
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    return {
        "text": data.decode("utf-8", errors="replace"),
        "truncated": truncated,
        "size_bytes": evidence.size_bytes,
    }


def content_disposition(evidence: Evidence) -> str:
    safe = (
        evidence.original_filename.replace('"', "")
        .replace("\r", "")
        .replace("\n", "")
    )
    return f'inline; filename="{safe}"'
