# Limitations and Caveats

## Evidence integrity

- SHA-256 verification proves that the stored bytes match the digest recorded at intake.
- It does not prove that the file was authentic before acquisition.
- It is not a chain-of-custody record by itself.
- Red Thread stores files under generated names and never modifies the original bytes after intake,
  but custody procedures remain the investigator's responsibility.

## Timestamps

- Syslog timestamps usually omit the year and timezone. Red Thread records inferred years and
  assumed timezones explicitly.
- A log that crosses a year boundary may require a manual year correction.
- Financial/call/chat evidence defaults to `Asia/Kolkata`; other deployments must configure the
  appropriate timezone.
- Temporal proximity is a lead, not proof of a relationship.

## Parsing

- The parsers support the documented formats and conservative column aliases. Unusual schemas
  may require a parser extension or explicit mapping.
- Unknown lines and malformed records are preserved as warnings, not silently treated as facts.
- Generic text/CSV/JSON fallbacks do not claim semantic understanding.
- OCR, EXIF and compression analysis can produce false positives or false negatives.
- ELA is meaningful mainly for lossy JPEG; it is skipped for lossless PNG.
- An OCR result is not ground truth.
- The invoice parser handles common label/value PDFs and tables; complex layouts may need
  manual review.

## Correlation and provenance

- Exact normalized identifiers are linked as exact matches.
- Co-mention, temporal, spatial, communication-sequence and device/auth links are persisted as
  classified leads with support rows and source locators; they are not findings or proof.
- Spatial proximity requires documented coordinates and context. It does not establish presence
  for an interval, movement between points, or association.
- Red Thread does not use fuzzy similarity or name-only matching to merge people.
- Every relationship can be reviewed and annotated; accepted review does not convert a lead into
  proof.
- Shared identifiers are investigative correlations, not proof of common ownership or intent.
- Relationships are scored by a fixed-weight linear model (`services/ml_ranker.py`) that reads only
  features the deterministic rule already computed. The score is a **ranking signal in [0, 1]**.
  It is not a probability of guilt, fraud, identity or causation, and it never creates a
  relationship or changes its type or classification.
- The scorer has no training step and no model artefact, so it is fully auditable but also limited:
  it orders leads, it does not discover new kinds of connection.
- Pseudonymisation before external AI is pattern- and entity-driven. An identifier present in
  neither the entity table nor a recognised pattern can survive. Treat it as a strong reduction of
  exposure, not a guarantee of anonymity.

## Authentication rules

- Threshold-based alerts are indicators, not proof of compromise.
- Legitimate user error, scanners, NAT sharing, stale credentials, and authorized testing can
  produce the same patterns.
- The auth log's line 412 and burst data in the demo are synthetic.
- Live monitoring is optional, CLI-only in this build, and restricted to an explicitly
  configured source. The web API does not expose arbitrary-path monitoring.

## AI

- AI output is an interpretation, not evidence.
- Citations are validated structurally against stored records and the retrieved context, but a
  structurally valid citation does not guarantee that the model's reasoning is correct.
- Insufficient evidence should produce an explicit insufficiency response; investigators must
  still verify this.
- External AI processing sends selected excerpts to a third party. Use only if authorized and
  consistent with the provider's terms.
- Identifiers are pseudonymised locally before sending, but this is a reduction of exposure, not a
  guarantee of anonymity. See `AI_INTEGRATION.md`.
- Red Thread does not claim that external processing is private or compliant for every dataset.
- No live provider connection is claimed in the test results unless a real request succeeded.

## Reports and legal use

- Reports are marked **DRAFT — HUMAN REVIEW REQUIRED**.
- They are not automatically court-admissible.
- The court-oriented format follows the sections and the Section 63 certificate fields described in
  the Schedule to the Bharatiya Sakshya Adhiniyam, 2023. It is a preparation aid, not a filing.
- Every declaration, device identifier, signature, place and signing date in the Section 63
  annexure is left **blank on purpose**. Red Thread cannot attest to a device it never examined.
- The report cannot independently be submitted as a legally valid report. Review, verification and
  completion by the appropriate party and expert are required.
- Red Thread does not sign, attest, or fabricate an examiner's signature, and does not guarantee
  admissibility.
- Findings do not establish guilt, fraud, authenticity, or intent.
- Reports include annotations, review decisions and audit events, but those are human records,
  not independent verification.

## Deployment and access control

- The default deployment is single-investigator and local.
- There is no full multi-user identity, role, or permission system.
- Case-scoped API checks prevent cross-case access through the documented routes, but anyone
  with local filesystem access can read the SQLite database and evidence directory.
- The deployed demo has no login or authentication. Its API, evidence, reports, annotations and
  AI endpoints are public; use synthetic data only. Add proper identity, authorization, rate
  limiting, backups and storage encryption before handling real case material.
- The spatial map loads tiles from the configured provider (OpenStreetMap by default); set a
  local/neutral tile URL when network leakage or offline operation matters.

## Demo data

- All Operation PhishTrace, Benign Control and Operation Digital Trail files are synthetic.
- The PhishTrace screenshot is generated with Pillow and its PDF uses `INR` for font
  compatibility. The auth log is padded to preserve documented locators.
- Operation Digital Trail uses fictional phones, devices, accounts, IPs and coordinates. Its
  relationships are generated by the deterministic rules, not hardcoded.
- `sample_data/manifest.json` is for convenience; Red Thread computes its own hashes on upload.
- Do not present any synthetic data as real evidence.
