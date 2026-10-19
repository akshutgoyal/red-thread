#!/usr/bin/env python3
"""Copy the local Red Thread cases, records and files into Supabase + R2.

The cloud credentials are read from a temporary environment file, for example
backend/.env.cloud. That file is gitignored and must never be committed.

Usage:
    backend/.venv/bin/python scripts/migrate_local_to_cloud.py \
        --env-file backend/.env.cloud --replace

The source is the local SQLite database (default data/red-thread.db) and the
local evidence directory (data/evidence). The destination is the Postgres
database in RED_THREAD_DATABASE_URL and the R2 bucket in R2_BUCKET.

The migration copies the investigation records and evidence byte-for-byte, then
regenerates fresh Red Thread PDF and JSON reports from the migrated data. Old
local report files are not uploaded.

--replace removes remote cases whose titles match the local demo cases, plus
their R2 prefixes, before copying. It never removes other cases.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = PROJECT_ROOT / "data" / "red-thread.db"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        help="Optional env file containing RED_THREAD_DATABASE_URL, R2_* and RED_THREAD_STORAGE_BACKEND.",
    )
    parser.add_argument(
        "--source-db",
        help=f"Local SQLite database (default: {DEFAULT_SOURCE_DB}).",
    )
    parser.add_argument(
        "--data-dir",
        help=f"Local data directory containing evidence/ (default: {DEFAULT_DATA_DIR}).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete remote cases with the same titles and their R2 prefixes before copying.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.env_file:
        env_path = Path(args.env_file).expanduser().resolve()
        if not env_path.is_file():
            raise SystemExit(f"Environment file not found: {env_path}")
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)

    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.orm import Session

    from app.config import get_settings
    from app.database import Base
    from app.models import (
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
    )
    from app.services import report_service, storage_service

    settings = get_settings()
    remote_url = settings.resolved_database_url
    if remote_url.startswith("sqlite"):
        raise SystemExit(
            "RED_THREAD_DATABASE_URL is not set to Supabase/Postgres. "
            "Put the cloud credentials in the --env-file and try again."
        )
    if not settings.is_r2:
        raise SystemExit(
            "RED_THREAD_STORAGE_BACKEND is not r2. Set it to r2 and provide the R2_* values."
        )

    source_db = (
        Path(args.source_db).expanduser().resolve()
        if args.source_db
        else DEFAULT_SOURCE_DB
    )
    if not source_db.is_file() and not args.source_db:
        fallback = PROJECT_ROOT / "data" / "raksha.db"
        if fallback.is_file():
            source_db = fallback
    if not source_db.is_file():
        raise SystemExit(f"Local source database not found: {source_db}")

    data_dir = (
        Path(args.data_dir).expanduser().resolve()
        if args.data_dir
        else DEFAULT_DATA_DIR
    )

    local_engine = create_engine(
        f"sqlite:///{source_db}",
        connect_args={"check_same_thread": False},
    )
    remote_connect_args = (
        {"prepare_threshold": None}
        if remote_url.startswith("postgresql+psycopg://")
        else {}
    )
    remote_engine = create_engine(
        remote_url,
        connect_args=remote_connect_args,
        pool_pre_ping=True,
    )
    Base.metadata.create_all(bind=remote_engine)

    local = Session(local_engine)
    remote = Session(remote_engine, expire_on_commit=False)
    uploaded_evidence = 0
    reports_generated = 0
    warnings: list[str] = []
    deleted_prefixes = 0

    try:
        local_cases = list(local.scalars(select(Case)))
        if not local_cases:
            raise SystemExit("The local database contains no cases.")

        local_titles = [case.title for case in local_cases]
        conflicts = list(
            remote.scalars(select(Case).where(Case.title.in_(local_titles)))
        )
        if conflicts and not args.replace:
            raise SystemExit(
                "Remote cases with the same demo titles already exist. "
                "Re-run with --replace to replace only those cases and their R2 prefixes."
            )
        if conflicts:
            conflict_ids = [case.id for case in conflicts]
            for case in conflicts:
                remote.delete(case)
            remote.commit()
            for case_id in conflict_ids:
                for prefix in (f"evidence/{case_id}/", f"reports/{case_id}/"):
                    deleted_prefixes += storage_service.delete_prefix(prefix)
            print(
                f"Replaced {len(conflicts)} remote demo case(s); "
                f"deleted {deleted_prefixes} R2 object(s)."
            )

        copy_order = [
            Case,
            Evidence,
            Event,
            Entity,
            EventEntity,
            Finding,
            FindingEvidence,
            GraphEdge,
            AuditEvent,
            AiQuery,
        ]
        counts: dict[str, int] = {}

        for model in copy_order:
            rows = list(local.scalars(select(model)))
            for row in rows:
                values = {
                    column.key: getattr(row, column.key)
                    for column in inspect(model).columns
                }

                if model is Evidence:
                    relative = row.relative_path
                    key = (
                        relative
                        if relative.startswith("evidence/")
                        else storage_service.evidence_key(
                            row.case_id, row.stored_filename
                        )
                    )
                    local_file = data_dir / relative
                    if local_file.is_file():
                        storage_service.save_bytes(
                            key,
                            local_file.read_bytes(),
                            content_type=row.media_type
                            or storage_service.content_type_for(key),
                        )
                        uploaded_evidence += 1
                    else:
                        warnings.append(
                            f"Missing local evidence file: {local_file} (key {key})"
                        )
                    values["relative_path"] = key

                remote.merge(model(**values))

            remote.commit()
            counts[model.__name__] = len(rows)
            print(f"  {model.__name__}: {len(rows)}")

        local_case_ids = [case.id for case in local_cases]
        migrated_cases = list(
            remote.scalars(select(Case).where(Case.id.in_(local_case_ids)))
        )
        for case in migrated_cases:
            for report_type in ("pdf", "json"):
                report_service.generate_report(remote, case.id, report_type)
                reports_generated += 1
    finally:
        remote.close()
        local.close()

    print("\nMigration complete.")
    print(f"  Source database: {source_db}")
    print(f"  R2 bucket: {settings.r2_bucket}")
    print(f"  Evidence files uploaded: {uploaded_evidence}")
    print(f"  Red Thread reports generated: {reports_generated}")
    print(f"  Rows copied: {counts}")
    if warnings:
        print("  Warnings:")
        for warning in warnings:
            print(f"    - {warning}")
    print(
        "\nThe exact local case IDs and records are now in Supabase/R2. "
        "Render can keep RED_THREAD_SEED_DEMO=true; the seed will skip these case titles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
