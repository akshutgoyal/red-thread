"""Backfill provenance-backed relationships from legacy GraphEdge rows.

This is additive and idempotent. It does not delete cases, evidence, findings or
legacy graph edges.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", help="Backfill only one case")
    parser.add_argument("--env-file", help="Optional dotenv file for database settings")
    args = parser.parse_args()

    if args.env_file:
        from dotenv import load_dotenv

        env_path = Path(args.env_file).expanduser()
        if not env_path.is_file():
            raise SystemExit(f"Env file does not exist: {env_path}")
        load_dotenv(env_path, override=False)

    sys.path.insert(0, str(BACKEND_ROOT))

    from app.database import Base, SessionLocal, engine
    from app.models import Relationship
    from app.services import relationship_service

    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        result = relationship_service.backfill_legacy_graph_edges(
            session, case_id=args.case_id
        )
        total = session.query(Relationship).count()
        print(
            "Legacy graph edges materialized: "
            f"{result['relationships']} relationships, "
            f"{result['supports']} support rows; "
            f"{total} relationships now stored."
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
