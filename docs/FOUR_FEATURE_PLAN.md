# Four Feature Improvements — Implementation Plan

Grounded in an inspection of the existing codebase at `64457d1`. Nothing here
rebuilds an existing module; each item extends what is already implemented.

## What already exists (inspection result)

| Capability | Where | Reused for |
| --- | --- | --- |
| Deterministic correlation engine | `services/relationship_engine.py` | Item 3 (ML ranking on top) |
| Persisted relationships + supports | `models/relationship.py`, `relationship_service` | Items 1, 3, 4 |
| Context builder for prompts | `ai_service._build_context` | Item 1 (pseudonymisation hook) |
| PII redaction | `ai_service._redact_text` / `_redact_value` | Item 1 (replaced by pseudonyms) |
| Entity extraction | `utils/extraction.extract_entities` | Item 1 (identifies what to pseudonymise) |
| PDF report generator | `services/report_service.py` (ReportLab) | Item 2 |
| Audit trail | `AuditEvent`, `audit_service` | Item 2 chain of custody |
| Reconstruction workspace | `CrimeReconstructionPage.tsx` + `reconstruction_service` | Item 4 |
| Count definitions | `count_service.case_counts` | Items 3, 4 |

## Item 1 — Privacy-preserving AI

**Layer:** `services/privacy_service.py` (new), called from `ai_service._build_context`.

- Build a `Pseudonymizer` per request. Walk the serialized context and replace
  identifiers with stable tokens: `PERSON_01`, `PHONE_01`, `EMAIL_01`,
  `ACCOUNT_01`, `UPN_01`, `DEVICE_01`, `IP_01`, `MAC_01`, `LOCATION_01`,
  `ORG_01`, `EVIDENCE_01`, `EVENT_01`, `FINDING_01`, `REL_01`.
- Record IDs (`evidence:`/`event:`) are already opaque hashes; they are
  pseudonymised too so the model cannot correlate across sessions.
- Store the mapping **in memory only** for the duration of the request. It is
  never written to the database, logged, or sent to the provider.
- Keep the structure identical so cross-source analysis still works.
- De-pseudonymise the model's answer server-side before it reaches the
  investigator, but only for tokens that exist in this request's mapping. An
  unknown token is left as-is and flagged, so the model cannot invent identities.
- Citations are validated against real records *after* de-pseudonymisation, so
  the existing validation path is unchanged.

**Config:** `RED_THREAD_AI_PSEUDONYMIZE_PII` (default `true`). When `false`,
behaviour falls back to the existing `ai_redact_pii` masking.

**Backwards compatibility:** the answer JSON keys, citation verification,
`AiQuery` persistence and all existing tests stay identical.

## Item 2 — Court-oriented report (mock)

Extend `report_service._build_pdf` with the sections the current PDF lacks, and
verify every field against the BSA Schedule (checked against published
descriptions of Sections 63(2) and 63(4) and the Schedule):

1. Case information and investigation details — **exists**
2. Structured evidence register — **extend** (add intake time, parser, integrity)
3. Evidence source and provenance — **add**
4. Chain-of-custody records — **add** (derived from `AuditEvent`)
5. SHA-256 and integrity status — **exists**
6. Chronological timeline — **exists**
7. Cross-source correlation findings — **exists** (8.1)
8. Supporting evidence per finding — **exists**
9. Verified / observation / inferred / AI distinction — **add explicit legend**
10. Limitations and human review notes — **exists**
11. Section 63 certificate annexure — **rewrite** against the Schedule

**Annexure fields (from the Schedule):** Part A — tick-box source type, make,
model, colour, serial number, IMEI/UIN/UID/MAC/Cloud ID, lawful-control
declaration, device-working-properly declaration, owned/maintained/managed by
signer, hash value + algorithm, hash report enclosed, date (DD/MM/YYYY), time
(IST, 24h), place, signature. Part B — same identifier block plus independent
technical confirmation of source and hash and the expert's signature.

**Non-fabrication rule:** every declaration field is emitted **blank** with a
"to be completed by" note. Red Thread never emits a declaration, a signature, a
certification, a place, a date of signing or a device serial it does not have.

**Disclaimer block** on page 1, in the annexure, and in the JSON metadata.

## Item 3 — Lightweight multi-type correlation

The engine already produces eight relationship types (`shared_identifier`,
`co_mention`, `temporal_association`, `spatial_proximity`,
`communication_sequence`, `device_auth_context`, `geo_velocity_anomaly`,
`cctv_coverage_gap`). The gap is that detection method and score are not exposed
per relationship.

- Add `services/ml_ranker.py`: a small, dependency-free logistic-style scorer
  over engineered features (shared identifier count, temporal delta bucket,
  spatial distance bucket, same-evidence flag, event-type overlap, support
  count, repeated-interaction count). Deterministic weights, no training.
- Store the result in the existing `metadata_json` under `ml_assist`
  (`detection_method`, `score`, `features`, `explanation`). No migration.
- Never overwrite a deterministic relationship's type. ML only (a) ranks and
  (b) proposes `ml_lead`-style suggestions for pairs the rules did not already
  link, always `classification=inference`, `review_status=unreviewed`.
- Expose `detection_method` and `score` in `RelationshipRead`, the graph edge,
  and the report.
- The score is a **match score**, never a probability of guilt or fraud.

## Item 4 — Crime Reconstruction integration

The workspace, tabs, sequence endpoint and redirects were built in the previous
change (`64457d1`). This item closes the remaining integration gaps:

- Link reconstructed events to the relationship graph and entity explorer.
- Add an evidence-reference indicator per event with a direct link.
- Surface AI-assisted leads as a distinct category in the Findings tab.
- Add a compact confidence/uncertainty legend to the overview.
- Verify no duplicate event/entity/relationship reads and consistent counts.

## Test plan

| Area | Test |
| --- | --- |
| Privacy | pseudonyms are stable, reversible, absent from the outbound payload |
| Privacy | no mapping is persisted or logged |
| Report | every required section present; no fabricated declaration |
| ML | deterministic matches unchanged; score exposed; no type overwrite |
| Reconstruction | tabs render, counts consistent, links resolve |
