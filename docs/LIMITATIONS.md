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

## Correlation

- Exact normalized identifiers are linked as exact matches.
- Heuristic temporal links are labelled `heuristic` and are not persisted as findings.
- Red Thread does not use fuzzy similarity to merge entities.
- Shared identifiers are investigative correlations, not proof of common ownership or intent.

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
- Red Thread does not claim that external processing is private or compliant for every dataset.
- No live provider connection is claimed in the test results unless a real request succeeded.

## Reports and legal use

- Reports are marked **DRAFT — HUMAN REVIEW REQUIRED**.
- They are not automatically court-admissible.
- The Section 63 BSA section is a preparation template with blank signature fields.
- Red Thread does not sign, attest, or fabricate an examiner's signature.
- Findings do not establish guilt, fraud, authenticity, or intent.

## Deployment and access control

- The default deployment is single-investigator and local.
- There is no full multi-user identity, role, or permission system.
- Case-scoped API checks prevent cross-case access through the documented routes, but anyone
  with local filesystem access can read the SQLite database and evidence directory.
- The deployed demo has no login or authentication. Its API, evidence, reports and AI endpoints
  are public; use synthetic data only. Add proper identity, authorization, rate limiting, backups
  and storage encryption before handling real case material.

## Demo data

- All Operation PhishTrace and benign-control files are synthetic.
- The screenshot is generated with Pillow.
- The PDF uses `INR` for font compatibility.
- The auth log is padded with blank lines to preserve documented locators.
- `manifest.json` is for convenience; Red Thread computes its own hashes on upload.
- Do not present synthetic data as real evidence.
