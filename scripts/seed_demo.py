#!/usr/bin/env python3
"""Seed the synthetic Operation PhishTrace demo through the Red Thread API.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --include-benign
    python scripts/seed_demo.py --base-url http://127.0.0.1:8000

The backend must already be running. This script uploads the synthetic files,
parses them, runs deterministic reconciliation, and prints the resulting case
ID. It never calls the AI provider.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = PROJECT_ROOT / "sample_data"

MEDIA_TYPES = {
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

OPERATION_FILES = [
    "call_log.csv",
    "chat_export.txt",
    "invoice_45000.pdf",
    "payment_screenshot.png",
    "upi_transaction_log.csv",
    "auth.log",
]
BENIGN_FILES = ["invoice_legit.pdf", "upi_statement.csv"]


def wait_for_backend(client: httpx.Client, attempts: int = 20) -> None:
    for attempt in range(1, attempts + 1):
        try:
            response = client.get("/api/health")
            if response.status_code == 200:
                payload = response.json()
                print(
                    f"Backend online: database={payload.get('database')} "
                    f"ocr={payload.get('ocr_available')} "
                    f"ai={payload.get('ai_provider')}"
                )
                return
        except httpx.HTTPError:
            pass
        if attempt < attempts:
            time.sleep(0.5)
    raise SystemExit(
        "Backend is not reachable. Start it with:\n"
        "  cd backend\n"
        "  .venv/bin/python -m uvicorn app.main:app --reload --port 8000"
    )


def create_case(client: httpx.Client, title: str, description: str) -> dict:
    response = client.post(
        "/api/cases",
        json={"title": title, "description": description},
    )
    response.raise_for_status()
    return response.json()


def upload(client: httpx.Client, case_id: str, path: Path) -> dict:
    media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    with path.open("rb") as handle:
        response = client.post(
            f"/api/cases/{case_id}/evidence",
            files={"file": (path.name, handle, media_type)},
        )
    response.raise_for_status()
    return response.json()


def parse(client: httpx.Client, case_id: str, evidence: dict) -> dict:
    response = client.post(
        f"/api/evidence/{evidence['id']}/parse",
        params={"case_id": case_id},
    )
    if response.status_code == 409:
        response = client.post(
            f"/api/evidence/{evidence['id']}/parse",
            params={"case_id": case_id, "reparse": "true"},
        )
    response.raise_for_status()
    return response.json()


def seed_case(
    client: httpx.Client,
    *,
    title: str,
    description: str,
    directory: Path,
    files: list[str],
) -> str:
    case = create_case(client, title, description)
    print(f"\nCase created: {case['id']} - {case['title']}")
    evidence = []
    for name in files:
        path = directory / name
        if not path.exists():
            raise SystemExit(
                f"Missing {path}. Run: python sample_data/generate_sample_data.py"
            )
        item = upload(client, case["id"], path)
        evidence.append(item)
        print(f"  uploaded {name}  sha256={item['sha256'][:16]}...")

    for item in evidence:
        result = parse(client, case["id"], item)
        print(
            f"  parsed   {item['original_filename']}  "
            f"parser={result['parser_name']} events={result['events_created']} "
            f"findings={result['findings_created']} status={result['status']}"
        )

    reconciled = client.post(f"/api/cases/{case['id']}/reconcile")
    reconciled.raise_for_status()
    print(f"  reconciliation findings: {reconciled.json()['findings_created']}")

    findings_response = client.get(f"/api/cases/{case['id']}/findings")
    findings_response.raise_for_status()
    findings = findings_response.json()["items"]
    print("  findings:")
    for finding in findings[:20]:
        print(f"    [{finding['severity']:8}] {finding['title']}")
    if len(findings) > 20:
        print(f"    ... {len(findings) - 20} more")

    print(f"\nOpen the case at: http://localhost:5173/cases/{case['id']}")
    return case["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--case-title",
        default="Operation PhishTrace (Synthetic Demo)",
    )
    parser.add_argument("--include-benign", action="store_true")
    args = parser.parse_args()

    if not SAMPLE_ROOT.exists():
        raise SystemExit(f"Sample data directory not found: {SAMPLE_ROOT}")

    with httpx.Client(base_url=args.base_url, timeout=180.0) as client:
        wait_for_backend(client)
        operation_id = seed_case(
            client,
            title=args.case_title,
            description=(
                "Synthetic Operation PhishTrace demonstration. All files are "
                "generated test data and are not real evidence."
            ),
            directory=SAMPLE_ROOT / "operation_phishtrace",
            files=OPERATION_FILES,
        )
        if args.include_benign:
            seed_case(
                client,
                title="Benign Control (Synthetic Demo)",
                description=(
                    "Synthetic benign control with a matching invoice and UPI "
                    "statement. Reconciliation should validate the arithmetic."
                ),
                directory=SAMPLE_ROOT / "benign_control",
                files=BENIGN_FILES,
            )
        print(f"\nOperation case ID: {operation_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
