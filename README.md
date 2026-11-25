# Red Thread

**From fragmented digital traces to an explainable, human-reviewed investigation picture.**

Red Thread is a local-first digital forensics investigation framework. It preserves evidence
integrity, parses heterogeneous evidence into one canonical event model, correlates identifiers
across sources, reconstructs timelines and movement, surfaces deterministic discrepancies, and
produces a court-oriented draft report. AI assistance is optional, evidence-grounded, and
privacy-preserving. The deterministic pipeline works with no AI configured at all.

The defining property of the system is **epistemic honesty**. Every statement it produces is
labelled with what kind of statement it is: a direct observation, a deterministic rule match, a
correlation candidate, an inference, or a hypothesis. A lead is never upgraded into proof, a
citation is never fabricated, and a legal certificate is never signed on anyone's behalf.

---

## Table of contents

- [What it does](#what-it-does)
- [What it does not do](#what-it-does-not-do)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Setup](#setup)
- [Running the application](#running-the-application)
- [Loading the demo data](#loading-the-demo-data)
- [Usage guidelines](#usage-guidelines)
- [Evidence formats](#evidence-formats)
- [How analysis works](#how-analysis-works)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Project structure](#project-structure)

---

## What it does

**Evidence handling**

- Isolated investigation cases; every record is scoped to one case.
- Evidence stored byte-for-byte under a generated filename, with the original name kept as
  metadata only. Uploaded content is never executed.
- SHA-256 computed at intake, re-verifiable on demand to prove the stored bytes are unchanged.
- Provenance on every derived record: the evidence file plus the exact source locator
  (`line:12`, `row:4`, `page:2`, `message:7`, `trackpoint:9`).

**Analysis**

- 13 parsers: SSH/auth logs, call records (CDR), chat exports, UPI/bank transactions, invoices,
  email (CSV and EML), GPS (CSV/GPX/KML), CCTV metadata, device logs, images (OCR + EXIF), and
  generic text/CSV/JSON.
- One canonical event model that keeps the raw timestamp beside the normalized one, and labels how
  confident that normalization is.
- Entity extraction: phones, emails, UPI VPAs, accounts, UTRs, transaction IDs, invoice IDs, IPs,
  MACs, device IDs, usernames, domains, URLs, filenames, amounts.
- Provenance-backed relationships across sources with eight distinct connection types, each with
  its rule, supporting locators, classification and confidence.
- A lightweight scoring layer that ranks leads. It never creates a relationship and never changes a
  relationship's type.
- Deterministic reconciliation that produces findings with severity, limitations and alternative
  explanations.
- Unified timeline, a map of documented coordinates only, and a consolidated Crime Reconstruction
  workspace with six tabs.

**Output**

- PDF and JSON reports, including an evidence register, provenance, chain-of-custody derived from
  the audit trail, an integrity table, a timeline, correlation findings, a classification legend,
  and a Section 63 BSA certificate annexure with every prescribed field left deliberately blank.
- An optional assistant that answers questions from stored records, with validated citations and
  local pseudonymisation before anything is sent to an external provider.

**Guidance**

- An 11-stage investigation journey derived from real case state.
- A 48-step interactive tour across five tours that highlight real application controls.
- Contextual page guides ("what this is / when to use it / what to do next") that adapt to live
  case state.
- One-line explanations for 22 technical terms.

---

## What it does not do

These are deliberate design decisions, not missing features.

- It does not prove guilt, fraud, authenticity or criminal intent.
- It does not claim a burst of failed logins, an OCR anomaly or a compression artifact proves
  compromise or manipulation.
- It does not sign, attest or fabricate a Section 63 BSA certificate.
- It does not claim generated reports are automatically court-admissible.
- It does not execute uploaded content.
- It does not silently switch AI providers or fall back to a different model after a failure.
- It does not invent citations when the provider fails or evidence is insufficient.
- It does not merge people using fuzzy or name-only matching.
- It does not infer routes, locations or movement that were not documented in the evidence.
- It does not let the scoring layer create or reclassify a relationship.
- It does not discard real relationships to make displayed counts agree; it explains the
  difference instead.

---

## Architecture

```
React 19 + Vite + TypeScript + Tailwind
  Dashboard - Cases - Case overview - Crime reconstruction
  Evidence vault - Evidence intake - Entity explorer - Extracted events
  Relationship graph (Cytoscape) - Auth analysis - AI assistant - Reports
  Timeline / Locations / Findings (tabs inside Crime reconstruction)
                    |
                REST /api
                    |
FastAPI + Pydantic v2 + SQLAlchemy 2.0
  Auth, session, demo TTL, rate limiting, CSRF origin check
  Parser registry (13 parsers) -> canonical events -> entities
  Correlation engine (8 rule families) -> Relationship + Supports
  Lead scorer (fixed weights, explainable)
  Reconciliation (4 check families) -> Findings
  Count service (single source of truth)
  Guidance / narrative / reconstruction services
  ReportLab PDF + JSON report
  AI adapter + privacy (pseudonymisation) layer
                    |
    data/evidence/<case_id>/<generated>     data/red-thread.db
    reports/<case_id>/<file>                (SQLite locally, Postgres deployed)
```

Storage is abstracted. `RED_THREAD_STORAGE_BACKEND=local` writes to `data/` and `reports/`;
`r2` uses private Cloudflare R2 objects streamed through the API. Anonymous object URLs are never
issued.

---

## Requirements

| Component | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 is used by the Docker image |
| Node.js | 20.19+ or 22.12+ | Required by Vite 7 |
| npm | 10+ | |
| Tesseract | optional | Only needed for OCR on images |

Without Tesseract, image uploads still work; the parser records a warning instead of failing.

Every dependency, pinned version and system prerequisite is listed in
[REQUIREMENTS.md](REQUIREMENTS.md).

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests
pip install -r requirements-ocr.txt   # optional OCR
cp .env.example .env
```

If you use `uv`:

```bash
cd backend
uv venv .venv --python 3.12
uv pip install -r requirements.txt --python .venv/bin/python
uv pip install -r requirements-dev.txt --python .venv/bin/python
```

Edit `backend/.env` if needed. The defaults work for local development: SQLite, local storage,
localhost CORS.

### 2. Frontend

```bash
cd frontend
npm install --include=dev
cp .env.example .env.local     # optional; leave VITE_API_BASE_URL unset for the dev proxy
```

### 3. Windows

The same steps apply, with these differences:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

See `docs/WINDOWS.md` for a longer troubleshooting guide.

---

## Running the application

Two processes. Backend first.

**Terminal 1 - backend**

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API: <http://127.0.0.1:8000/api/health>
- Interactive docs (development only; disabled in production):
  <http://127.0.0.1:8000/docs>

**Terminal 2 - frontend**

```bash
cd frontend
npm run dev
```

- App: <http://localhost:5173>
- Vite proxies `/api` to `http://127.0.0.1:8000`, so no CORS setup is needed locally.

**Sign in.** The app requires authentication by default (`RED_THREAD_AUTH_REQUIRED=true`). Two
options:

- **Explore demo workspace** - one click, no account, uses synthetic data only.
- **Google sign-in** - requires `GOOGLE_CLIENT_ID` to be set. If it is unset, the Google button is
  hidden and the demo workspace remains available.

To disable the auth gate entirely for local experimentation, set
`RED_THREAD_AUTH_REQUIRED=false`.

---

## Loading the demo data

There are three synthetic cases: Operation PhishTrace (payment fraud), Benign Control (a case that
must produce no high-severity anomaly), and Operation Digital Trail (call, chat, email, GPS, CCTV,
device and auth records).

### Option A - automatic seed on startup

```bash
# backend/.env
RED_THREAD_SEED_DEMO=true
```

Restart the backend. The three cases are created idempotently by title, so restarts do not
duplicate them.

### Option B - seed through the API

With the backend already running:

```bash
backend/.venv/bin/python scripts/seed_demo.py --include-benign --digital-trail
```

This uploads and parses the real files through the same pipeline the UI uses, then prints the case
IDs. It never calls the AI provider.

### Option C - generate fresh sample files

```bash
backend/.venv/bin/python sample_data/generate_sample_data.py
```

All generated files are synthetic and labelled as such.

> The demo data is fictional. It must never be presented as real evidence.

---

## Usage guidelines

The intended workflow, in order. Each stage is also tracked in the app, which derives progress from
stored records rather than from a checklist you tick.

### 1. Create a case

One case per investigation. Name it after the incident, and record scope and authorization in the
investigator notes. Every piece of evidence, every derived record and every report is scoped to
this case; cases cannot see each other's data.

### 2. Upload evidence

Drag files onto **Evidence intake**, or use the vault's upload control. Each file is stored
unchanged and hashed. Files are limited by `RED_THREAD_MAX_UPLOAD_MB` (default 50 MB).

### 3. Verify integrity

Run **Verify integrity** on each file you intend to rely on. This re-reads the stored object and
recomputes its SHA-256, recording the result in the audit trail.

What this proves: the stored bytes still match the digest recorded at intake.
What it does not prove: that the file was authentic before intake. Integrity is not
chain-of-custody, and it is not a substitute for a manual custody log.

### 4. Parse and review warnings

Select a file and run **Parse** (or **Reparse**). Parsing produces events and warning cards. Each
warning states what happened, why, how to fix it, and whether the data is still usable. Read those
before trusting a partially parsed file.

If a CSV or JSON file's columns cannot be interpreted confidently, it is held as **needs mapping**.
Choose which column maps to which field and save; the file is re-parsed with your mapping.

### 5. Check entities

**Entity explorer** lists every identifier extracted, with the number of events it appears in and
the evidence files it came from. A shared identifier is a correlation candidate, not proof that the
same person produced both records.

### 6. Review extracted events

**Extracted events** shows what each parser produced, with the original record beside it. Use
**Relevant**, **Needs review** and **Not relevant** deliberately: these decisions are written to the
audit trail and they drive the investigation progress.

### 7. Work the Crime reconstruction workspace

One sidebar entry, six tabs, in the order an investigation actually runs:

| Tab | Use it for |
|---|---|
| **Overview** | Case summary, key metrics, progress, and the confidence legend |
| **Event reconstruction** | The ordered sequence of what happened, each event linked to its evidence |
| **Timeline** | Chronology across all sources, with server-side filters |
| **Relationships** | Connected entities; opens the full graph |
| **Locations** | Documented coordinates only - no inferred routes |
| **Findings** | Observations, unresolved questions and AI-assisted leads |

Every reconstructed event carries a timestamp (or a time range), a description, related entities,
its source evidence and locator, related relationships, a review status and a confidence value.

The four confidence levels are not interchangeable:

- **Documented** - read directly from a stored record, or an exact rule match.
- **Supported** - backed by a cited source record you can open.
- **Possible correlation** - records relate in time, place or pattern. A lead, not a finding.
- **Uncertain** - the timestamp or the record is unreliable; ordering against it is indicative only.

### 8. Review relationships

Open any connection in the relationship graph to see the exact records behind it. Review decisions
are `accepted`, `rejected`, `needs_review` or `needs_more_evidence`, and they are recorded as an
immutable history as well as the current state.

**Accepting a relationship does not turn it into proof.** The classification and confidence stay as
they were. Accepting means "I have looked at this and it is worth keeping in view".

### 9. Review findings

Findings are deterministic discrepancies with a severity, a stated limitation and alternative
explanations. Review each high and critical finding before generating a report.

### 10. Use the AI assistant carefully

The assistant answers only from records in the current case and cites what it used. Every citation
is checked against the database and marked verified or flagged with a warning.

- Treat its output as interpretation, never as evidence.
- Check the citations yourself.
- Save anything useful as a hypothesis annotation rather than relying on the chat history.

### 11. Generate the report

Generate a PDF and/or JSON report from **Reports**. The report is marked **DRAFT - HUMAN REVIEW
REQUIRED**. It includes the evidence register, SHA-256 values, provenance, chain-of-custody from the
audit trail, the timeline, findings, and a Section 63 BSA annexure whose fields are intentionally
blank.

The report is a preparation aid. It is not a filing, and it is not court-admissible on its own.

### Keyboard and navigation notes

- Old routes still work: `/timeline`, `/spatial`, `/findings` and `/workspace` redirect into the
  matching reconstruction tab, and deep links such as `?event=` and `?finding=` are preserved.
- Press **Esc** to exit a guided tour. Tours never block navigation.
- The theme toggle follows your OS preference on first load and remembers your choice.

---

## Evidence formats

| Type | Extensions | What is extracted |
|---|---|---|
| Auth log | `.log`, `.txt` | Login success/failure, sessions, sudo, burst and brute-force indicators |
| Call records | `.csv`, `.json` | Caller, receiver, direction, duration, cell tower, device |
| Chat export | `.txt`, `.json`, `.jsonl` | Messages, senders, timestamps, attachments, amounts |
| Transactions | `.csv`, `.json` | Amount, currency, payer, payee, UTR, transaction ID, VPA, status |
| Invoices | `.pdf`, `.csv`, `.json` | Invoice ID, line items, tax, total, payee, date |
| Email | `.eml`, `.csv` | Sender, recipient, subject, date, body, attachment names |
| GPS | `.csv`, `.json`, `.gpx`, `.kml` | Latitude, longitude, timestamp, place label |
| CCTV metadata | `.csv`, `.json` | Camera/site, segment start, recording end, location |
| Device logs | `.csv`, `.json`, `.jsonl` | Device ID, IMEI/IMSI, account, event type |
| Images | `.png`, `.jpg`, `.jpeg` | OCR text (with Tesseract) and EXIF GPS |
| Generic | `.txt`, `.csv`, `.json` | Best-effort events, with a warning that interpretation was limited |

Column names are matched case-insensitively and tolerate common aliases. When matching is not
confident, the file is held for explicit column mapping rather than guessed at.

---

## How analysis works

### Correlation

Relationships are built only from stored rows, and every one carries its supporting locators:

| Relationship | Meaning | Classification |
|---|---|---|
| `shared_identifier` | Same normalized identifier in two different evidence files | correlation |
| `co_mention` | Two entities named in the same event | observation |
| `temporal_association` | Same identifier, events inside the temporal window | correlation |
| `spatial_proximity` | Documented coordinates within a radius and time window | correlation |
| `communication_sequence` | Several communications sharing an identifier in a window | hypothesis |
| `device_auth_context` | Authentication and device records sharing an identifier | correlation |
| `geo_velocity_anomaly` | Implied travel speed above a review threshold | hypothesis |
| `cctv_coverage_gap` | Gap between consecutive segments of one camera | hypothesis |

Rebuilding is idempotent. Stale auto-generated rows are removed, but reviewed or annotated
relationships are never deleted.

### Lead scoring

A fixed-weight linear scorer ranks relationships using features the rules already computed (shared
identifier, co-mention, temporal proximity, spatial proximity, repetition, device context,
cross-source corroboration, and a penalty when a rule fired without a supporting locator).

It is deliberately not a trained model: no dependency, no training pipeline, no artefact, and the
same input always produces the same score. The score is exposed as a **match score in 0 to 1** and
is a ranking signal only. It is never a probability of guilt, fraud or identity.

### Counts

One service computes every count. The dashboard, workspace, graph and report all read it, so they
cannot disagree. Where two numbers differ (for example unique connections versus total
relationships), the difference is explained rather than hidden.

### Privacy of AI requests

Before anything leaves the process, identifiers are replaced with stable tokens (`PERSON_01`,
`PHONE_01`, `ACCOUNT_01`, ...). The same value maps to the same token within a request, so
cross-source reasoning still works. The token-to-value map exists only in memory for that one
request: it is never stored, logged, or sent to the provider. Answers are mapped back on the server,
so you read real identifiers while the provider only ever saw tokens.

This reduces exposure. It is not a guarantee of anonymity: an identifier that appears in neither the
case entity table nor a recognised pattern can survive.

---

## Configuration

Settings are read from `backend/.env` or a project-root `.env` and use the `RED_THREAD_` prefix,
except provider credentials. Copy `backend/.env.example` and adjust. Never commit `.env`.

### Core

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_DATA_DIR` | `<project>/data` | Local evidence root |
| `RED_THREAD_REPORTS_DIR` | `<project>/reports` | Local report root |
| `RED_THREAD_DATABASE_URL` | SQLite in data dir | SQLite or a Postgres URI |
| `RED_THREAD_ENVIRONMENT` | `development` | Enables production-only behaviour |
| `RED_THREAD_MAX_UPLOAD_MB` | `50` | Per-file upload limit |
| `RED_THREAD_CORS_ORIGINS` | localhost dev origins | Comma-separated allowlist |
| `RED_THREAD_STORAGE_BACKEND` | `local` | `local` or `r2` |
| `RED_THREAD_SEED_DEMO` | `false` | Create the three demo cases on startup |
| `RED_THREAD_SAMPLE_DATA_DIR` | `<project>/sample_data` | Seed source directory |

### Cloudflare R2 (only when the storage backend is `r2`)

| Variable | Purpose |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret |
| `R2_BUCKET` | Private bucket name |
| `R2_ENDPOINT` | Optional explicit endpoint |
| `R2_REGION` | Signing region, default `auto` |

### Authentication and access

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_AUTH_REQUIRED` | `true` | Enforce the auth gate |
| `RED_THREAD_SESSION_SECRET` | dev placeholder | JWT signing key; use `openssl rand -hex 32` |
| `RED_THREAD_SESSION_TTL_HOURS` | `168` | Session lifetime |
| `RED_THREAD_DEMO_COPY_TTL_HOURS` | `24` | Demo copy retention |
| `GOOGLE_CLIENT_ID` | empty | Google sign-in audience |

In production, a missing or short `RED_THREAD_SESSION_SECRET` is replaced with an ephemeral
per-process secret: forged tokens stay impossible, but sessions reset whenever the service restarts.
Set a real secret to keep users signed in.

### Rate limiting

| Variable | Default |
|---|---|
| `RED_THREAD_RATE_LIMIT_ENABLED` | `true` |
| `RED_THREAD_RATE_LIMIT_API_PER_MINUTE` | `120` |
| `RED_THREAD_RATE_LIMIT_AUTH_PER_MINUTE` | `10` |
| `RED_THREAD_RATE_LIMIT_DEMO_PER_10_MINUTES` | `3` |
| `RED_THREAD_RATE_LIMIT_AI_PER_MINUTE` | `8` |
| `RED_THREAD_RATE_LIMIT_UPLOADS_PER_MINUTE` | `30` |
| `RED_THREAD_TRUSTED_PROXY_HOPS` | `1` |

### Timestamps

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_AUTH_DEFAULT_TIMEZONE` | `UTC` | Timezone assumed for syslog lines |
| `RED_THREAD_DEFAULT_TIMEZONE` | `Asia/Kolkata` | Default for financial/call/chat evidence |
| `RED_THREAD_AUTH_DEFAULT_YEAR` | unset | Fixed syslog year; blank infers from the case date |

Assumptions are recorded on each event as a timestamp confidence value, never silently applied.

### Correlation thresholds

| Variable | Default |
|---|---|
| `RED_THREAD_CORRELATION_TEMPORAL_WINDOW_MINUTES` | `60` |
| `RED_THREAD_CORRELATION_SPATIAL_RADIUS_M` | `500` |
| `RED_THREAD_CORRELATION_SPATIAL_WINDOW_MINUTES` | `60` |
| `RED_THREAD_CORRELATION_MAX_PAIRS_PER_IDENTIFIER` | `50` |
| `RED_THREAD_CORRELATION_GEO_VELOCITY_KMH` | `200` |
| `RED_THREAD_CORRELATION_CCTV_GAP_MINUTES` | `5` |

### AI (all optional)

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_AI_PROVIDER` | `auto` | `auto`, `isoquant`, `commandcode`, `tokenharbor`, `none` |
| `RED_THREAD_AI_TIMEOUT_SECONDS` | `60` | Request timeout |
| `RED_THREAD_AI_MAX_RETRIES` | `2` | Retries for 429 and 5xx |
| `RED_THREAD_AI_MAX_CONTEXT_CHARS` | `60000` | Context ceiling |
| `RED_THREAD_AI_MAX_TOKENS` | `8192` | Completion budget; `16384` for large TokenHarbor contexts |
| `RED_THREAD_AI_BUDGET_USD` | `0.5` | Cumulative spend cap |
| `RED_THREAD_AI_PSEUDONYMIZE_PII` | `true` | Token substitution before sending |
| `RED_THREAD_AI_REDACT_PII` | `true` | Masks phone numbers and labeled account numbers |
| `ISOQUANT_API_KEY` / `COMMANDCODE_API_KEY` / `TOKENHARBOR_API_KEY` | empty | Provider credentials |

`auto` prefers Isoquant, then CommandCode, then TokenHarbor. With no key, the assistant page shows a
clear disabled state and every other feature works normally.

If a provider exhausts its token budget, Red Thread returns a `truncated_response` or
`reasoning_only` error instead of fabricating an answer.

### Other

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_ENABLE_LIVE_MONITOR` | `false` | Guard for optional live auth monitoring |
| `RED_THREAD_EXPOSE_API_DOCS` | unset | Force `/docs` on or off |
| `TESSERACT_CMD` | empty | Full path to the Tesseract binary if not on `PATH` |

---

## API reference

Base path `/api`. Case-scoped routes verify ownership; a missing case returns 404 and a case you do
not own returns 403.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | App, database, OCR and AI status |
| POST | `/auth/google` | Google credential sign-in |
| POST | `/auth/demo` | Start a demo session |
| POST | `/auth/logout` | Clear the session |
| GET | `/auth/me` | Current principal |
| GET/POST | `/cases` | List / create cases |
| GET/PATCH/DELETE | `/cases/{case_id}` | Read, update, delete a case |
| POST/GET | `/cases/{case_id}/evidence` | Upload / list evidence |
| GET | `/evidence/{evidence_id}` | Evidence metadata |
| POST | `/evidence/{evidence_id}/verify` | Recompute SHA-256 |
| POST | `/evidence/{evidence_id}/parse` | Parse and reconcile |
| GET/PUT | `/evidence/{evidence_id}/mapping` | Column mapping preview / save |
| GET | `/evidence/{evidence_id}/content` | Download or preview the stored file |
| GET | `/evidence/{evidence_id}/text` | Bounded text preview |
| GET | `/cases/{case_id}/events` | Filtered canonical events |
| GET | `/cases/{case_id}/timeline` | Dated and undated timeline |
| GET | `/cases/{case_id}/entities` | Extracted entities |
| GET | `/cases/{case_id}/entities/{entity_id}` | Entity detail |
| GET | `/cases/{case_id}/graph` | Graph nodes, edges and canonical counts |
| GET | `/cases/{case_id}/spatial` | Documented coordinate observations |
| GET | `/cases/{case_id}/reconstruction` | Reconstruction summary |
| GET | `/cases/{case_id}/reconstruction/sequence` | Event sequence |
| POST | `/cases/{case_id}/reconcile` | Re-run deterministic checks |
| GET | `/cases/{case_id}/findings` | Findings register |
| POST | `/findings/{finding_id}/review` | Review a finding |
| GET/POST | `/cases/{case_id}/relationships` | List relationships |
| GET | `/relationships/{relationship_id}` | Relationship detail with supports |
| POST | `/relationships/{relationship_id}/review` | Review a relationship |
| GET/POST | `/cases/{case_id}/annotations` | List / create annotations |
| POST | `/cases/{case_id}/events/{event_id}/review` | Review an extracted event |
| GET | `/cases/{case_id}/event-reviews` | All event reviews |
| GET | `/cases/{case_id}/guidance` | Stages, next step, attention list |
| GET | `/cases/{case_id}/narrative` | Case narrative |
| GET | `/cases/{case_id}/audit` | Audit trail |
| GET | `/cases/{case_id}/auth/export` | Auth export as JSON or CSV |
| GET | `/ai/status` | Provider configuration (`?check=true` for a live probe) |
| GET | `/cases/{case_id}/ai/suggestions` | Question prompts derived from case state |
| POST | `/cases/{case_id}/ai/ask` | Evidence-grounded answer |
| POST/GET | `/cases/{case_id}/reports` | Generate / list reports |
| GET | `/reports/{report_id}` | Report metadata |
| GET | `/reports/{report_id}/download` | Download the report |

Evidence, report and finding routes accept the case scope as a `case_id` query parameter or an
`X-Case-ID` header. Cross-case access is rejected.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/demo -c cookies.txt
curl http://127.0.0.1:8000/api/cases -b cookies.txt
```

---

## Testing

```bash
# Backend: 190 tests
cd backend
.venv/bin/python -m pytest

# Frontend: 54 tests
cd ../frontend
npm test

# Production build and lint
npm run build
npm run lint
```

Notes:

- Use `npm test` rather than calling `vitest` directly: the npm script pins `NODE_ENV=test`.
- Backend tests use a temporary SQLite database and never call a real AI provider.
- Frontend tests guard the guided tours: every anchor must exist, every step must be reachable on
  the route it navigates to, and no step may route through a redirect-only path.

---

## Deployment

The reference deployment is Vercel (frontend) plus Render (backend), with Supabase Postgres for
metadata and Cloudflare R2 for private evidence and report objects.

```
Vercel (React SPA)
  -> Render (FastAPI Docker, Tesseract, non-root)
       -> Supabase Postgres
       -> Cloudflare R2
       -> Isoquant / CommandCode / TokenHarbor (optional AI)
```

- `Dockerfile` builds the backend image; `render.yaml` is the Blueprint with its health check at
  `/api/health`.
- `frontend/vercel.json` sets the SPA rewrite, security headers and CSP.
- In deployed mode the API is stateless: Render's disk is ephemeral, Supabase and R2 persist.
  Render Free sleeps after inactivity and has 512 MB of RAM.
- Set `RED_THREAD_SESSION_SECRET` in production, or sessions reset on every restart.
- Set `RED_THREAD_CORS_ORIGINS` to the exact frontend origin, and `VITE_API_BASE_URL` to the API
  base ending in `/api`.
- `scripts/migrate_local_to_cloud.py` performs a resumable local-to-cloud migration preserving case
  IDs, records, audit history and evidence.

See `deploy/README.md` for the full walkthrough.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Authentication required` from the API | Sign in, or set `RED_THREAD_AUTH_REQUIRED=false` for local work |
| `Cross-site request blocked` | Your frontend origin is missing from `RED_THREAD_CORS_ORIGINS` |
| Google button missing | `GOOGLE_CLIENT_ID` is not set; use the demo workspace |
| Frontend calls reach the wrong host | `VITE_API_BASE_URL` must end in `/api` |
| Sessions reset after a restart | `RED_THREAD_SESSION_SECRET` is unset, so an ephemeral secret is used |
| CSV produces no events | Columns were not recognised: use the mapping UI, then reparse |
| OCR returns nothing | Tesseract is not installed, or `TESSERACT_CMD` points elsewhere |
| PDF parsing fails | Ensure `pdfplumber` is installed in the active environment |
| Port 8000 is busy | Run uvicorn on another port and update the Vite proxy |
| Reports list is empty | Generate one; the list starts empty by design |
| `npm` command not found | Reinstall Node.js with npm, then reopen the terminal |

---

## Limitations

- Single-investigator by default; there is no full multi-user permission model.
- SHA-256 proves stored-file correspondence, not pre-acquisition authenticity.
- Integrity records are not a chain-of-custody proof; a manual custody log is still required.
- Timestamp inference can be wrong across a year boundary; the assumption is recorded and labelled.
- OCR quality depends on Tesseract, fonts, image quality and language data.
- ELA is skipped for lossless PNG and is only an indicator for JPEG.
- Temporal proximity and spatial proximity are leads, never proof of association.
- The lead score is a ranking signal, not a probability of guilt, fraud or identity.
- AI answers can be wrong even when their citations are structurally valid.
- Pseudonymisation reduces exposure; it does not guarantee anonymity.
- Live monitoring is optional, disabled by default, and restricted to a configured source.
- The Section 63 annexure contains fields only; the formalities remain with the party and the expert.
- The report is a draft preparation aid and is not automatically court-admissible.
- Demo data is synthetic and must not be presented as real evidence.

See `docs/LIMITATIONS.md` for the full list.

---

## Project structure

```
red-thread/
  Dockerfile                 Render image (Tesseract, non-root user)
  render.yaml                Render Blueprint
  deploy/README.md           Vercel + Render + Supabase + R2 guide
  backend/
    app/
      main.py                App factory, middleware, security headers
      config.py              Settings (RED_THREAD_ prefix)
      database.py            Engine, sessions, lightweight migrations
      dependencies.py        Case scoping and ownership checks
      rate_limit.py          Per-route-class limits
      models/                16 SQLAlchemy models
      schemas/               Pydantic request and response models
      api/                   health, auth, cases, evidence, analysis,
                             guidance, relationships, ai, reports
      parsers/               13 parsers plus the registry
      services/              Parsing, correlation, scoring, reconciliation,
                             counts, guidance, narrative, reconstruction,
                             reports, AI, privacy, storage, demo
      utils/                 Timestamps, amounts, identifiers, geo, CSV safety
    tests/                   190 tests
    requirements*.txt
    .env.example
  frontend/
    src/
      api/                   Typed API client
      components/            UI, layout, guidance, tour engine
      context/               Active case, auth
      hooks/                 TanStack Query hooks
      lib/                   Formatting, glossary, severity
      pages/                 16 routed pages
      types/                 Shared TypeScript contracts
    vercel.json              SPA rewrite, headers, CSP
    vite.config.ts           /api dev proxy
  sample_data/               Synthetic demo cases
  scripts/                   Seed, migration, backfill
  docs/                      Architecture, AI, auth, demo, limitations
  data/                      Local evidence and SQLite database
  reports/                   Locally generated reports
```

---

## Documentation

- [Project documentation](docs/PROJECT_DOCUMENTATION.md) - problem statement, objectives, architecture, methodology, implementation, results, future scope
- [Architecture](docs/ARCHITECTURE.md)
- [AI integration and privacy](docs/AI_INTEGRATION.md)
- [Authentication parser](docs/AUTH_PARSER.md)
- [Demo walkthrough](docs/DEMO.md)
- [Operation Digital Trail](docs/OPERATION_DIGITAL_TRAIL.md)
- [Limitations and caveats](docs/LIMITATIONS.md)
- [Windows troubleshooting](docs/WINDOWS.md)
- [Requirements](REQUIREMENTS.md) - dependencies and software prerequisites

---

**Red Thread does not replace an investigator. It preserves provenance, exposes its reasoning, and
keeps conclusions subject to human review.**
