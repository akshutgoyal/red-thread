# Operation Digital Trail — synthetic PS3 demonstration

**Synthetic data only.** Every record in `sample_data/operation_digital_trail/` is fictional.
It is not real evidence and does not describe any real person, device, account or location.
The demonstration exists to exercise Red Thread's multi-source ingestion, provenance-backed
correlation, reconstruction and AI-grounding paths.

## Scenario

The case is deliberately small enough to review by hand. It combines:

| Source | Purpose |
|---|---|
| `call_log.csv` | Phone numbers, device IDs and cell-tower labels across three calls |
| `chat_export.txt` | Device, place, camera, IP and payment-reference co-mentions |
| `email_records.csv` | Sender/recipient, device, place and UTR references |
| `gps_records.csv` | Two documented `DEV-DT-01` fixes near Central Junction and one South Gate fix |
| `cctv_metadata.csv` | Camera coordinates and documented recording coverage windows |
| `device_log.csv` | IMEI, MSISDN, IP and account activity |
| `auth.log` | ISO-8601 authentication chronology around `198.51.100.77` |

The intended links are:

- phone `+91-99001-12233` across call, chat, email and device records;
- device `DEV-DT-01` / IMEI `356938035643809` across call, GPS and device records;
- IP `198.51.100.77` across authentication and device records;
- UTR `UTR-DT-778899` across chat and email records;
- documented GPS and CCTV observations at Central Junction within a bounded window.

These are **test correlations**, not proof of identity, causation or guilt. The graph does not
invent routes between isolated points and does not merge people by name.

## Generate and seed

```bash
# Regenerate all synthetic fixtures and sample_data/manifest.json
backend/.venv/bin/python sample_data/generate_sample_data.py

# Seed the running local API with the Digital Trail case
backend/.venv/bin/python scripts/seed_demo.py --digital-trail

# Or seed all demos
RED_THREAD_SEED_DEMO=true ...   # the app seeds all DEMO_CASES on startup
```

The API must be running for `scripts/seed_demo.py`. The script uploads through the real
evidence endpoint, parses each file, runs deterministic reconciliation, and prints the case ID.
The seed service is additive: existing PhishTrace and Benign Control cases are not deleted or
overwritten. Re-running the script creates a new synthetic case; the startup service is
idempotent by title.

## Expected investigation view

After parsing and reconciliation, the case should show:

- cross-source events from every source;
- entities for phones, accounts, devices, IMEI, IP, cameras, cell towers and GPS points;
- relationships carrying rule, classification, confidence, support rows, evidence/event IDs
  and source locators;
- exact identifier matches, co-mentions, temporal associations, spatial proximity,
  communication sequences, device/authentication context and a CCTV coverage gap;
- documented spatial points only;
- review and annotation controls.

Counts vary with parser and rule changes. Do not hardcode expected counts in the application;
inspect the generated records.

## Suggested AI prompt

Focus the assistant on `DEV-DT-01` or the case itself:

> Which evidence sources connect DEV-DT-01 to the Central Junction observations, and which
> connections are exact structured matches versus temporal, co-mention or spatial leads?
> Cite the evidence and event records and state what is still uncertain.

A grounded answer should separate exact structured values, textual co-mentions and correlation
leads. It must not claim that proximity proves identity or guilt.

## Report

Generate a JSON or PDF report from the case's Reports page or API. The report should contain
the evidence inventory and SHA-256 values, timeline, relationships and support rows, spatial
observations, findings, unresolved questions, investigator annotations, review decisions,
audit trail and the draft-only legal caution.

## Limitations

- All identifiers and coordinates are synthetic.
- Spatial proximity is a lead; it does not establish that a person or device was present for
  the whole interval.
- A shared device or IP is not proof of identity.
- Name-only associations are not merged.
- AI output is an interpretation, not evidence.
- Reports are drafts requiring human review and are not automatically court-admissible.
- The demo does not establish any real-world event.
