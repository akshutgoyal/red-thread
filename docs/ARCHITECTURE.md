# Architecture

## Runtime components

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React, Vite, TypeScript, Tailwind | Investigation UI and Cytoscape/Recharts visualizations |
| API | FastAPI, Pydantic | Validation, case-scoped routes, OpenAPI |
| Persistence | SQLAlchemy, SQLite or Postgres/Supabase | Cases, evidence, events, entities, findings, reports, audit, AI queries |
| File storage | Local filesystem or Cloudflare R2 | Evidence bytes and generated report files |
| Processing | Python standard library, pandas, pdfplumber, Pillow/pytesseract | Parsing, extraction, hashing, optional OCR |
| Correlation | NetworkX | In-memory relationship graph and evidence links |
| Reporting | ReportLab | PDF and JSON exports |
| AI | CommandCode Provider API or TokenHarbor | Optional evidence-grounded answers |

## Local and deployed modes

Local mode uses SQLite plus `data/` and `reports/`. The deployed mode uses Supabase Postgres
for metadata and private Cloudflare R2 objects for evidence/reports. The API is stateless:
Render’s ephemeral filesystem is not the system of record. `storage_service` maps keys such as
`evidence/<case_id>/<file>` and `reports/<case_id>/<file>` to either the local roots or R2.
Parsers materialize an R2 object to a temporary file, parse it, and remove the temporary copy.
The access-gated content and download endpoints stream bytes from local storage or R2.

A startup seed (`RED_THREAD_SEED_DEMO=true`) creates the two synthetic demo cases in the configured
database and storage. It is idempotent by case title. The deployment guide is
[deploy/README.md](../deploy/README.md).

## Request flow: evidence upload

1. The route validates the case and calls `evidence_service.create_evidence`.
2. The original filename is sanitized; the extension and size are validated.
3. The bytes are streamed through `storage_service` to `data/evidence/<case_id>/<uuid><ext>`
   in local mode or to the private R2 key `evidence/<case_id>/<uuid><ext>` while a SHA-256
   digest is computed in chunks.
4. An `Evidence` row stores original name, generated name, storage key, media type, size,
   digest, upload time, and status.
5. An audit event `evidence.uploaded` is recorded.
6. The original bytes are never modified by parsing, verification, or reporting.

## Request flow: parse and reconcile

1. `POST /api/evidence/{id}/parse` selects a parser through `parsers/registry.py`.
2. The parser receives a `ParserContext` containing case ID, evidence ID, source filename,
   reference date, default year, and the parser-appropriate timezone.
3. The parser returns canonical events plus warnings and metadata.
4. `investigation_service` persists events, creates/reuses entities, and records audit data.
5. Authentication alerts are converted into deterministic findings.
6. `reconciliation_service.run` rebuilds reconciliation findings and persisted graph edges.
7. Evidence status becomes `parsed`, `partially_parsed`, `ocr_unavailable`, or `failed`.

Re-parsing a file with `reparse=true` deletes its derived events and linked auth findings,
clears reconciliation findings/graph edges for the case, and rebuilds them from the current
evidence.

## Canonical event

Every parser produces `CanonicalEventDraft` objects with:

- `event_type`
- `timestamp_raw`
- `timestamp_normalized` (UTC when reliable)
- `timestamp_confidence`: `exact`, `inferred_year`, `ambiguous`, `unknown`
- `timestamp_timezone`
- `source_locator` (`line:12`, `row:19`, `page:1`, `bbox:x,y,w,h`, `message:3`)
- `source_snippet`
- `attributes`
- `entities`
- `warnings`

The database `Event` row additionally stores case ID, evidence ID, source filename, parser name,
parser version, and creation time.

## Entity normalization

| Entity type | Normalization | Preserved original |
|---|---|---|
| phone | Remove separators, retain leading `+`, do not guess a country code | yes |
| upi_vpa | Lowercase and trim | yes |
| ip | Canonicalized with `ipaddress` (IPv4/IPv6) | yes |
| utr | Trim, retain 12-digit reference | yes |
| transaction_id | Uppercase and trim | yes |
| invoice_id | Uppercase and trim | yes |
| email / url / domain | Lowercase | yes |
| filename | Lowercase | yes |
| account | Trim; only extracted when explicitly labeled | yes |
| amount | Decimal-normalized string plus original | yes |

Exact matching uses the normalized value. The original value remains available in the UI and
reports. Fuzzy similarity is not used to merge entities.

## Relationship graph

NetworkX builds an in-memory `MultiDiGraph` on request. Node IDs use stable prefixes:

- `evidence:<id>`
- `event:<id>`
- `entity:<id>`

Edge classes:

| Edge type | Method | Meaning |
|---|---|---|
| `evidence_contains_event` | containment | The event came from this evidence |
| `event_mentions_entity` | extraction | The parser extracted this entity from the event |
| `exact_identifier_match` | normalized_exact | Same normalized entity in different evidence |
| `exact_utr_match` | normalized_exact | Screenshot OCR and ledger share a UTR |
| `amount_conflict` | conflict | Deterministic amount mismatch |
| `payee_conflict` | conflict | Deterministic payee mismatch |
| `temporal_proximity` | heuristic | Timestamps close; explicitly a lead, not proof |

Persisted edges from reconciliation are merged into the graph. Temporal edges are computed only
when `include_temporal=true` and are never persisted as findings.

## Reconciliation checks

`reconciliation_service.py` performs:

- Screenshot OCR amount vs transaction ledger amount (exact UTR required for the comparison).
- Screenshot/invoice payee vs transaction recipient.
- Invoice total vs matching transaction amount.
- Invoice subtotal + declared tax = total.
- Declared tax rates vs tax amounts where available.
- Shared identifiers across evidence sources.
- Timestamp confidence/uncertainty per evidence.
- Benign arithmetic reconciliation (informational finding).

Findings are cleared and rebuilt on each reconciliation run, so repeated runs do not duplicate
them. Authentication findings are created separately and are not cleared by financial
reconciliation.

## Database tables

`cases`, `evidence`, `events`, `entities`, `event_entities`, `findings`, `finding_evidence`,
`graph_edges`, `audit_events`, `ai_queries`, `reports`.

The database schema is created with `Base.metadata.create_all` during the FastAPI lifespan.
To reset a local development database, stop the backend and remove `data/red-thread.db` and
`data/evidence/`. To reset the deployed demo, delete the two synthetic cases in Supabase and
their R2 prefixes; see [deploy/README.md](../deploy/README.md).

## Security boundaries

- Uploaded content is never executed.
- Stored names are generated; original names are metadata only.
- `evidence_service.get_evidence_path` resolves paths and rejects anything outside the evidence
  root.
- Evidence, finding and report routes validate case ownership.
- Optional `RED_THREAD_API_TOKEN` requires a bearer token or `X-API-Key`.
- AI keys remain backend-only.
- Reports expose relative identifiers, never arbitrary server paths.

## Failure behavior

- Unsupported parser: HTTP 422 with the supported format list.
- Already parsed without `reparse=true`: HTTP 409.
- Hash mismatch: verification returns `verified=false` and an audit event.
- OCR unavailable: status `ocr_unavailable`, not a clean result.
- AI unconfigured: HTTP 503 with configuration instructions.
- AI provider error: structured HTTP error; no fabricated answer.
- Report file missing: HTTP 404; path traversal is rejected.

## Frontend theme and design system

- `src/theme/ThemeContext.tsx` owns the `light`/`dark` theme, applies the `dark` class to
  `<html>`, sets `color-scheme`, and persists the choice to `localStorage`
  (`red-thread-theme`).
- `index.html` contains a pre-mount bootstrap script that applies the stored or system theme
  before React renders, preventing a flash of the wrong theme.
- `src/index.css` defines semantic RGB-channel variables for both themes: app, surface,
  surface-2/3, line, line-strong, primary, secondary, muted, accent, chart colors and graph
  colors. Tailwind maps these to `bg-app`, `bg-surface`, `border-line`, `text-primary`,
  `text-muted`, `bg-accent`, and related utilities.
- Charts use `var(--chart-*)` colors and disable animation for stable, reproducible rendering.
- The Cytoscape graph selects light/dark node, label, border and edge palettes from
  `GRAPH_PALETTES` and uses the `.graph-canvas` CSS background.
- The layout is responsive: the sidebar becomes a mobile drawer below `lg`; the evidence table
  collapses Type/Uploaded below `2xl` (full details remain in the drawer); buttons use
  `whitespace-nowrap`; all controls expose focus-visible rings.
- `prefers-reduced-motion` disables transitions and animations.
