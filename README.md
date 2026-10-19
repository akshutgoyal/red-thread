# Red Thread

**From fragmented digital traces to an explainable, human-reviewed investigation picture.**

Red Thread is an indigenous, local-first digital forensics investigation framework. It preserves
evidence integrity, extracts structured events, correlates identifiers across sources,
reconstructs timelines, identifies deterministic discrepancies, visualizes relationships, and
generates traceable reports. AI assistance is optional and evidence-grounded; the deterministic
pipeline works without it.

> **Status:** Working end-to-end implementation with a synthetic demonstration case. Backend:
> 78 automated tests passing. Frontend: production build and lint passing. AI integration includes
> mocked failure tests and a live DeepSeek V4.1 Flash verification via TokenHarbor with validated
> citations. A managed deployment path (Vercel + Render + Supabase + Cloudflare R2) is included.

---

## What Red Thread does

- Creates isolated investigation cases.
- Stores uploaded evidence without modification and records a SHA-256 digest.
- Recalculates hashes to verify stored-file integrity.
- Parses SSH authentication logs, call logs, chats, UPI/bank transactions, invoices,
  email, generic text/CSV/JSON, and images with optional OCR.
- Normalizes events and extracts entities (phones, VPAs, UTRs, IPs, usernames, invoice IDs,
  transaction IDs, filenames, URLs, emails).
- Builds a cross-source relationship graph with exact matches, deterministic conflicts, and
  clearly labelled heuristic leads.
- Builds a unified timeline that preserves raw timestamps, inferred years, and timezone
  assumptions.
- Runs deterministic reconciliation checks for amount discrepancies, payee mismatches, exact
  UTR matches, GST arithmetic, shared identifiers, and timestamp uncertainty.
- Produces reviewable findings with severity, limitations, alternative explanations, and
  source locators.
- Supports investigator review decisions and notes.
- Generates PDF and JSON reports with hashes, provenance, findings, limitations, audit history,
  and a draft-only Section 63 BSA preparation section.
- Optionally answers investigator questions through CommandCode's DeepSeek V4.1 Flash endpoint
  or TokenHarbor's OpenAI-compatible endpoint, with citation validation.

## What Red Thread does not do

- It does not prove guilt, fraud, authenticity, or criminal intent.
- It does not claim that an SSH burst, OCR anomaly, or compression artifact proves compromise
  or manipulation.
- It does not automatically sign or attest a Section 63 BSA certificate.
- It does not claim that generated reports are automatically court-admissible.
- It does not execute uploaded content.
- It does not silently switch to another AI provider or a local model.
- It does not invent AI citations when the provider fails or the evidence is insufficient.

---

## Architecture

```
React + Vite + TypeScript + Tailwind
  Dashboard · Cases · Evidence · Auth analysis · Timeline
  Cytoscape relationship graph · Findings · AI assistant · Reports
                              │
                         REST /api
                              │
FastAPI + Pydantic + SQLAlchemy + SQLite
  Case service · Evidence service · Hashing service
  Parser registry → canonical events → entities
  NetworkX correlation · Timeline · Reconciliation
  ReportLab PDF/JSON reports · Optional AI adapter
                              │
              data/evidence/<case_id>/<generated-name>
              data/red-thread.db
              reports/<case_id>/<report-file>
```

Local mode uses SQLite plus the local `data/` and `reports/` directories. The deployed mode
uses the same services with a storage abstraction:

```text
Vercel (React frontend)
  → Render (FastAPI Docker service, Tesseract)
      → Supabase Postgres (metadata, events, findings, audit)
      → Cloudflare R2 (evidence files and generated reports)
      → TokenHarbor / CommandCode (optional AI)
```

The API is stateless in deployed mode. Evidence and reports are private R2 objects; the API
streams them through the access-gated endpoints. See [deploy/README.md](deploy/README.md).

### Frontend and theme

The interface has a persistent light/dark theme toggle in the top bar and sidebar. On first
load it follows the operating-system preference; the choice is stored in `localStorage` under
`red-thread-theme` and applied before React mounts to avoid a flash of the wrong theme. The design
uses semantic CSS variables (`app`, `surface`, `line`, `primary`, `secondary`, `muted`,
`accent`) shared by every page, so cards, tables, forms, findings, charts and the Cytoscape
graph adapt consistently. The layout is responsive: the sidebar becomes a mobile drawer,
low-priority evidence columns collapse into the detail drawer, and interactive controls have
visible focus states. The app shell keeps the sidebar, top bar and footer pinned while the main
investigation area scrolls independently, on desktop and mobile. Charts use real stored data
only and render without animation for stable output.

### Investigation workflow

```
Ingest → hash & preserve → parse & normalize → extract entities
      → correlate → reconstruct timeline → generate findings
      → human review → export report
```

### Evidence classes

| Class | Examples | Treatment |
|---|---|---|
| Direct observation | raw log line, transaction row | Preserved with source locator |
| Deterministic rule | failed-login burst, amount mismatch | Rule ID and explanation |
| Exact identifier match | same UTR, same VPA, same phone | `normalized_exact` edge |
| Heuristic correlation | timestamps close together | Labelled lead; not proof |
| AI interpretation | summary or hypothesis | Always labelled AI-generated |
| Unverified hypothesis | unresolved investigative idea | Requires further evidence |

---

## Project structure

```
red-thread/
├── Dockerfile                       Render backend image with Tesseract
├── render.yaml                      Render Blueprint (free Docker web service)
├── .dockerignore
├── deploy/
│   └── README.md                    Vercel + Render + Supabase + R2 guide
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI factory, lifespan, startup seed
│   │   ├── config.py                settings, Postgres/R2 configuration
│   │   ├── database.py              SQLite/Postgres engine and session
│   │   ├── dependencies.py          case scoping and access-token gate
│   │   ├── models/                  SQLAlchemy models
│   │   ├── schemas/                 Pydantic request/response models
│   │   ├── api/                     health, cases, evidence, AI, reports
│   │   ├── services/                evidence, storage, hashing, investigation,
│   │   │                            correlation, reconciliation, AI, reports,
│   │   │                            demo seed
│   │   ├── parsers/                 canonical base, registry, auth adapter,
│   │   │                            call/chat/transaction/invoice/email/
│   │   │                            image/generic parsers
│   │   └── utils/                   timestamps, amounts, identifiers
│   ├── tests/                       78 backend tests
│   ├── requirements.txt             runtime dependencies
│   ├── requirements-dev.txt         test dependencies
│   ├── requirements-ocr.txt         optional OCR dependencies
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                     typed API client
│   │   ├── components/              UI, layout, charts
│   │   ├── context/                 active-case context
│   │   ├── hooks/                   TanStack Query hooks
│   │   ├── lib/                     formatting, severity and class helpers
│   │   ├── pages/                   dashboard, cases, evidence, auth, timeline,
│   │   │                            graph, findings, AI, reports
│   │   └── types/                   shared TypeScript types
│   ├── package.json
│   ├── vercel.json                  Vite build and SPA rewrite
│   └── vite.config.ts
├── sample_data/
│   ├── generate_sample_data.py      creates all synthetic demo files
│   ├── manifest.json                synthetic file hashes
│   ├── operation_phishtrace/        six synthetic evidence files
│   └── benign_control/              legitimate invoice + UPI statement
├── scripts/
│   └── seed_demo.py                 uploads and processes the demo via the API
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AI_INTEGRATION.md
│   ├── AUTH_PARSER.md
│   ├── DEMO.md
│   ├── LIMITATIONS.md
│   └── WINDOWS.md
├── data/                            local-mode evidence and SQLite database
├── reports/                         local-mode generated reports
├── README.md
└── .gitignore
```

---

## Quick start (Linux/macOS)

### 1. Prerequisites

- Python **3.11+** (this workspace used Python 3.14 with `uv`).
- Node.js **20+** and npm **10+**.
- Optional OCR: Tesseract (`tesseract --version`). On Arch: `sudo pacman -S tesseract tesseract-data-eng`.
- Optional PDF parsing: `pdfplumber` is installed from `requirements.txt`.

### 2. Backend

```bash
cd red-thread/backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt     # tests
pip install -r requirements-ocr.txt    # optional OCR
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

If you use `uv`, the equivalent is:

```bash
cd red-thread/backend
uv venv .venv --python 3.14
uv pip install -r requirements.txt --python .venv/bin/python
uv pip install -r requirements-dev.txt --python .venv/bin/python
uv pip install -r requirements-ocr.txt --python .venv/bin/python
uv run python -m uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for the OpenAPI interface and
`http://127.0.0.1:8000/api/health` for health status.

### 3. Frontend

```bash
cd red-thread/frontend
npm install --include=dev
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`.

### 4. Generate the synthetic demo data

From the project root:

```bash
backend/.venv/bin/python sample_data/generate_sample_data.py
```

All generated files are labelled synthetic. The generator creates the PDFs, screenshot,
CSV/text files, and `manifest.json`.

### 5. Seed the demo case

With the backend running:

```bash
backend/.venv/bin/python scripts/seed_demo.py --include-benign
```

The script prints the case ID, parser results, findings, and the frontend URL. It does not call
AI.

### 6. Run the tests

```bash
cd backend
.venv/bin/pytest -q           # 78 passed
cd ../frontend
npm run build                 # TypeScript + Vite production build
```

---

## Windows PowerShell setup

These commands assume the project is at `C:\red-thread`.

### 1. Install prerequisites

- Python 3.12+ from <https://www.python.org/downloads/windows/>. Enable **Add Python to PATH**.
- Node.js 20+ from <https://nodejs.org/>.
- Optional Tesseract from <https://github.com/UB-Mannheim/tesseract/wiki>. Note its path.

Verify:

```powershell
py --version
node --version
npm --version
tesseract --version
```

### 2. Backend

```powershell
cd C:\red-thread\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-ocr.txt
Copy-Item .env.example .env
notepad .env
python -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Frontend

Open a second PowerShell window:

```powershell
cd C:\red-thread\frontend
npm install --include=dev
npm run dev
```

Open <http://localhost:5173>.

### 4. Generate and seed the demo

Open a third PowerShell window:

```powershell
cd C:\red-thread
.\backend\.venv\Scripts\python.exe sample_data\generate_sample_data.py
.\backend\.venv\Scripts\python.exe scripts\seed_demo.py --include-benign
```

### 5. Tests

```powershell
cd C:\red-thread\backend
.\.venv\Scripts\pytest.exe -q

cd C:\red-thread\frontend
npm run build
```

### Common Windows issues

| Problem | Fix |
|---|---|
| `python` opens the Microsoft Store | Use `py -3.12` or disable the App Execution Alias. |
| Activation is blocked | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| `tesseract` not found | Install Tesseract and set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `backend\.env`. |
| `npm` is not recognized | Reinstall Node.js with the npm component and reopen PowerShell. |
| Port 8000 is busy | `python -m uvicorn app.main:app --port 8001` and set `VITE_API_BASE_URL`/proxy accordingly. |
| CORS error | Ensure the frontend origin is in `RED_THREAD_CORS_ORIGINS`. |
| SQLite path error | Use an absolute path for `RED_THREAD_DATA_DIR` if the relative path is unclear. |
| Long path errors | Enable long paths in Windows or place the project at `C:\red-thread`. |
| `esbuild` install script blocked | Run `npm install-scripts approve esbuild` or use a normal npm configuration. |
| PDF parsing fails | Ensure `pdfplumber` is installed in the active environment. |
| OCR returns no text | Verify Tesseract, its language data, and the `TESSERACT_CMD` path. |

See [docs/WINDOWS.md](docs/WINDOWS.md) for a longer troubleshooting guide.

---

## Deployed mode (Vercel + Render + Supabase + Cloudflare R2)

The managed free-tier deployment is documented in [deploy/README.md](deploy/README.md). It uses:

- **Vercel** for the React/Vite frontend.
- **Render** for the FastAPI Docker service (Tesseract included; free plan sleeps after inactivity).
- **Supabase Postgres** for cases, evidence metadata, events, findings and audit records.
- **Cloudflare R2** for private evidence and report objects.
- **TokenHarbor** or **CommandCode** for optional AI.

The app remains local-first by default. Set `RED_THREAD_STORAGE_BACKEND=r2`, provide
`RED_THREAD_DATABASE_URL` and the `R2_*` credentials, and set `RED_THREAD_SEED_DEMO=true` to create
the two synthetic demo cases on startup. The seed is idempotent by case title. It creates the
same PhishTrace and benign-control content with new case IDs. For the exact local snapshot,
use `scripts/migrate_local_to_cloud.py` (see `deploy/README.md`, section 5b); it copies the
local case IDs, records, audit/AI-query history and evidence, and regenerates Red Thread reports.

The deployed demo is public: there is no login or access gate. The API, evidence, reports and
AI endpoints are public, so use synthetic evidence only. CORS is controlled by the comma-separated
`RED_THREAD_CORS_ORIGINS` allowlist; trailing slashes are normalized.

The deployed API is stateless: Render’s disk is ephemeral; Supabase and R2 retain data across
restarts. Render Free has 512 MB RAM and cold starts, and Supabase Free projects may pause
after inactivity. The Docker image is in `Dockerfile`; the Render Blueprint is `render.yaml`;
the Vercel project root must be `frontend` and includes `frontend/vercel.json`.

---

## Configuration

Copy `backend/.env.example` to `backend/.env` (or the project-root `.env`). Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `RED_THREAD_DATA_DIR` | `<project>/data` | Local evidence root; local mode only |
| `RED_THREAD_REPORTS_DIR` | `<project>/reports` | Local report root; local mode only |
| `RED_THREAD_DATABASE_URL` | SQLite in data dir | SQLite, or a Postgres/Supabase URI (converted to psycopg) |
| `RED_THREAD_STORAGE_BACKEND` | `local` | `local` or `r2` |
| `R2_ACCOUNT_ID` | empty | Cloudflare account ID; required for R2 |
| `R2_ACCESS_KEY_ID` | empty | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | empty | R2 API token secret |
| `R2_BUCKET` | empty | Private R2 bucket name |
| `R2_ENDPOINT` | derived | Optional explicit R2 endpoint |
| `R2_REGION` | `auto` | R2 signing region |
| `RED_THREAD_SEED_DEMO` | `false` | Idempotently create the two synthetic demo cases on startup |
| `RED_THREAD_SAMPLE_DATA_DIR` | `<project>/sample_data` | Seed source directory |
| `RED_THREAD_MAX_UPLOAD_MB` | `50` | Per-file upload limit |
| `RED_THREAD_CORS_ORIGINS` | localhost dev origins | Comma-separated allowed frontend origins; trailing slashes are normalized |
| `RED_THREAD_AUTH_DEFAULT_TIMEZONE` | `UTC` | Timezone assumed for syslog auth lines |
| `RED_THREAD_DEFAULT_TIMEZONE` | `Asia/Kolkata` | Default for financial/call/chat evidence |
| `RED_THREAD_AUTH_DEFAULT_YEAR` | unset | Fixed year for syslog lines; blank infers from case date |
| `RED_THREAD_ENABLE_LIVE_MONITOR` | `false` | Guard for optional live auth monitoring |
| `RED_THREAD_AI_PROVIDER` | `auto` | `auto`, `commandcode`, `tokenharbor`, `none` |
| `RED_THREAD_AI_TIMEOUT_SECONDS` | `60` | Provider request timeout |
| `RED_THREAD_AI_MAX_RETRIES` | `2` | Retries for 429 and 5xx responses |
| `RED_THREAD_AI_MAX_CONTEXT_CHARS` | `60000` | Maximum evidence context sent to the model |
| `RED_THREAD_AI_MAX_TOKENS` | `8192` | Completion budget; use `16384` for TokenHarbor reasoning |
| `RED_THREAD_AI_REDACT_PII` | `true` | Masks phone numbers and labeled account numbers |
| `COMMANDCODE_API_KEY` | empty | CommandCode Provider API key |
| `COMMANDCODE_BASE_URL` | `https://api.commandcode.ai/provider/v1` | Official provider base URL |
| `COMMANDCODE_MODEL` | `deepseek/deepseek-v4.1-flash` | Verified model ID |
| `COMMANDCODE_ZDR` | `true` | Sends `x-cmd-zdr: 1` |
| `TOKENHARBOR_API_KEY` | empty | TokenHarbor fallback key |
| `TOKENHARBOR_BASE_URL` | `https://tokenharbor.ai/v1` | OpenAI-compatible base URL |
| `TOKENHARBOR_MODEL` | `deepseek-v4.1-flash:free` | Verified model ID |
| `TESSERACT_CMD` | empty | Optional full path to the Tesseract binary |

### AI provider selection

`RED_THREAD_AI_PROVIDER=auto` prefers `COMMANDCODE_API_KEY`, then `TOKENHARBOR_API_KEY`, and
otherwise disables AI. Set an explicit provider to override. There is no silent fallback to a
different provider or a local model after a configured provider fails.

- **CommandCode:** `POST https://api.commandcode.ai/provider/v1/chat/completions`,
  `Authorization: Bearer <key>`, model `deepseek/deepseek-v4.1-flash`. API access requires a
  CommandCode plan other than Go. The CLI key is the same key. Optional ZDR header
  `x-cmd-zdr: 1`.
- **TokenHarbor:** `POST https://tokenharbor.ai/v1/chat/completions`,
  `Authorization: Bearer <key>`, model `deepseek-v4.1-flash:free`.

The model on both routes is **DeepSeek V4.1 Flash**. The `provider` field (and the
`COMMANDCODE_API_KEY` / `TOKENHARBOR_API_KEY` choice) identifies the API transport; the UI
badges display the model name and expose the transport only as metadata.

**Reasoning-token budget:** DeepSeek V4.1 Flash may spend tokens on hidden reasoning before it
emits the final JSON. `RED_THREAD_AI_MAX_TOKENS` defaults to `8192`; for TokenHarbor with a large case
context, `16384` is recommended. If the budget is exhausted, Red Thread returns a
`truncated_response` or `reasoning_only` error instead of fabricating an answer. Lower
`RED_THREAD_AI_MAX_CONTEXT_CHARS` if a provider has a smaller output limit.

**Live verification (2026-10-19):** `GET /api/ai/status?check=true` succeeded against TokenHarbor
for `deepseek-v4.1-flash:free` (about 2.1 s). A live question on the seeded Operation PhishTrace
case returned HTTP 200 with 20 citations, all 20 validated, `validation_status=validated`, and
about 23.7 s latency. The configured AI page was also exercised in the browser: a live question
about the screenshot amount discrepancy returned a grounded answer with 4/4 validated citations,
uncertainties, alternatives, and next steps. No key is stored in the repository.

The AI is optional. Without a key, the assistant page shows a clear disabled state and the
deterministic pipeline remains fully functional.

**Privacy:** AI requests send only selected case excerpts. Review the provider's data-handling
terms before sending confidential evidence. The UI warns when an AI operation will use an
external provider. API keys never reach the browser and are never included in reports or logs.

---

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | App, database, OCR and AI status |
| GET/POST | `/api/cases` | List/create cases |
| GET/PATCH | `/api/cases/{case_id}` | Read/update a case |
| POST/GET | `/api/cases/{case_id}/evidence` | Upload/list evidence |
| GET | `/api/evidence/{evidence_id}?case_id=` | Evidence metadata |
| POST | `/api/evidence/{evidence_id}/verify?case_id=` | Recompute SHA-256 |
| POST | `/api/evidence/{evidence_id}/parse?case_id=` | Parse and reconcile |
| GET | `/api/evidence/{evidence_id}/content?case_id=` | Controlled file download/preview |
| GET | `/api/evidence/{evidence_id}/text?case_id=` | Bounded text preview |
| GET | `/api/cases/{case_id}/events` | Filtered canonical events |
| GET | `/api/cases/{case_id}/timeline` | Dated and undated timeline |
| GET | `/api/cases/{case_id}/entities` | Extracted entities |
| GET | `/api/cases/{case_id}/graph` | Cytoscape nodes and edges |
| GET | `/api/cases/{case_id}/findings` | Findings register |
| POST | `/api/findings/{finding_id}/review?case_id=` | Investigator review |
| POST | `/api/cases/{case_id}/reconcile` | Rerun deterministic checks |
| GET | `/api/cases/{case_id}/auth/export?format=json\|csv` | Auth event/finding export |
| GET | `/api/cases/{case_id}/audit` | Audit trail |
| GET | `/api/ai/status` | Provider configuration status |
| POST | `/api/cases/{case_id}/ai/ask` | Evidence-grounded AI question |
| POST/GET | `/api/cases/{case_id}/reports` | Generate/list reports |
| GET | `/api/reports/{report_id}?case_id=` | Report metadata |
| GET | `/api/reports/{report_id}/download?case_id=` | Download report |

Case-scoped routes validate that the case exists. Evidence/report/finding routes require the
selected `case_id` (query parameter or `X-Case-ID` header) and reject cross-case access. The
deployed API is public; there is no user authentication or access token.

---

## Synthetic demo: Operation PhishTrace

`sample_data/operation_phishtrace/` contains six **synthetic** files:

| File | Key content |
|---|---|
| `call_log.csv` | 10:15 call from `+91-98765-43210`, row 4 |
| `chat_export.txt` | demand at line 12; invoice attachment at line 14 |
| `invoice_45000.pdf` | `INV-2026-9912`, total `INR 45,000`, payee `gov-security@upi` |
| `payment_screenshot.png` | OCR text `INR 4,500.00`, VPA `gov-security@upi`, UTR `312456789012` |
| `upi_transaction_log.csv` | row 19: UTR `312456789012`, `45,000`, payee `fraud-mule@okaxis` |
| `auth.log` | failed burst from `203.0.113.45`; accepted key login at line 412 from `103.21.244.2` |

Expected deterministic output:

- Exact UTR match between screenshot OCR and ledger (informational).
- High-severity amount discrepancy: 4,500 vs 45,000.
- High-severity payee mismatch: `gov-security@upi` vs `fraud-mule@okaxis`.
- Shared phone, VPA and filename correlation findings.
- Authentication indicators for the failed-login burst, kept separate from the financial events.
- A benign control case that reconciles and does **not** produce a high/medium reconciliation
  anomaly.

The auth log is padded with blank lines so that the documented line 412 locator remains stable.
The screenshot is generated with Pillow, not captured from a real payment app. The PDF uses
`INR` for font compatibility. See [sample_data/operation_phishtrace/README.md](sample_data/operation_phishtrace/README.md).

**Source-package note:** the requested `SUTRAM_2026_Flagship_Solution_Package(1).zip` was not
present in the workspace. The available `SUTRAM_2026_Flagship_Solution_Package.zip` contains
five Markdown documents and no actual sample evidence. The `auth_parser.py` supplied at
`~/Sutram/auth_parser.py` was inspected and integrated. The demo files are therefore synthetic,
clearly labelled, and generated from the documented scenario rather than presented as supplied
source data.

---

## Authentication parser

The existing parser was preserved and refactored into
`backend/app/parsers/auth_log_parser.py` and wrapped by `auth_adapter.py`.

Preserved capabilities:

- SSH successful and failed login detection.
- Session opened/closed events.
- Sudo command events.
- Failed-login burst, persistent-failure, multiple-username and invalid-user rules.
- Suspicion scoring, JSON export, CSV export, and optional live monitoring.
- Default burst threshold: 8 failures in 60 seconds.
- Default persistent threshold: 10 failures in 15 minutes.

Corrections:

- Removed the hardcoded year `2000`. Missing years are inferred from the case/reference date and
  recorded with a warning and a confidence label.
- Moved CLI argument parsing and execution behind `main()` / `if __name__ == "__main__"`.
- Added IPv4 and IPv6 validation.
- Added accurate source line numbers and raw-line preservation.
- Unified batch and live detection on the same engine.
- Made thresholds configurable.
- Deduplicated incremental alert reasons.
- Preserved malformed lines as warnings instead of silently dropping them.

CLI examples:

```bash
cd backend
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log --year 2026 --json out.json --csv out.csv
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log --live --from-start
```

A burst threshold is a configured indicator, not proof of an attack. See
[docs/AUTH_PARSER.md](docs/AUTH_PARSER.md).

---

## Reports and legal caution

Reports include case metadata, evidence inventory, SHA-256 hashes, integrity results, parser
metadata, timeline events, findings, graph summaries, audit history, limitations, and a
clearly labelled AI-generated section.

Every report is marked **DRAFT — HUMAN REVIEW REQUIRED** and is not automatically
court-admissible. The Section 63 BSA section is a preparation template only. It contains blank
signature fields and must be reviewed, completed and signed by the appropriate authorized person.
Red Thread never fabricates a signature or attests on behalf of an investigator.

---

## Security and privacy

- Evidence files are stored under generated names; original names are metadata.
- Path traversal and unsafe paths are rejected.
- Uploaded content is never executed.
- File size, extension and empty-file validation are enforced.
- SHA-256 verification proves stored-file correspondence, not pre-acquisition authenticity.
- Case-scoped access checks prevent cross-case evidence/report access through the API.
- The deployed demo has no authentication gate. The API, case data, evidence, reports and AI
  endpoints are public; use synthetic evidence only and do not upload sensitive material.
- In deployed mode, R2 stays private and evidence/report bytes are streamed by the API; Supabase
  stores metadata. Secrets stay in Render’s environment, never in the frontend or repository.
- AI keys stay in backend environment variables and are never returned by the API.
- AI context is bounded, evidence excerpts are delimited as untrusted, and citations are
  validated against stored records.
- AI prompts explicitly prohibit tool use, file access, SQL, evidence modification, and
  independent approval of findings.
- AI failures do not affect stored evidence or deterministic results.
- No API key or raw evidence is written to application logs by the AI service.

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for the full limitation list.

---

## Test results

At the time of writing:

- **Backend:** `78 passed` with `pytest -q`.
- **Frontend:** `npm run build` completed successfully (TypeScript + Vite).
- **Frontend lint:** `npm run lint` completed with 0 errors and 0 warnings.
- The Vite production build is split into React, query, Cytoscape and Recharts vendor chunks.
- **Storage tests:** local round-trip, path-traversal rejection, and an R2 adapter round-trip
  using a fake S3 client. The live R2 path is verified by the cloud migration below.
- **Deployment-path verification:** a fresh SQLite/local-storage run with
  `RED_THREAD_SEED_DEMO=true` recreated the two cases (Operation PhishTrace: 6 evidence, 69 events,
  17 findings; Benign Control: 2 evidence, 3 events, 4 findings). The public API listed the
  cases, and streamed evidence and report downloads worked. The browser loaded the screenshot
  preview and generated a report through the public API.
- **Docker verification:** the Render image built successfully and ran as the non-root `red-thread`
  user. Health reported `database=ok` and `ocr_available=true`; the startup seed produced the same
  two cases and counts inside the container.
- **Postgres verification:** a temporary PostgreSQL 16 instance created the schema, seeded both
  cases (Operation PhishTrace: 6/69/17; Benign Control: 2/3/4), generated a JSON report, and
  returned the same counts through the API.
- **Migration verification:** the resumable script copied the exact local data into a temporary
  PostgreSQL 16 + Moto S3 environment, then into the live Supabase project and real R2 bucket
  through the session pooler. Live final state: the exact local IDs, 2 cases, 8 evidence files,
  72 events, 21 findings, 10 AI queries, 45 audit events, 60 graph edges and 4 Red Thread
  reports; 12 R2 objects (8 evidence + 4 reports). The previous seed cases and their objects
  were removed. Render health reports `database=ok`, AI configured and OCR available.
- **Remaining deployment config:** the Vercel frontend must use
  `https://red-thread-api.onrender.com/api` as `VITE_API_BASE_URL`, and Render’s
  `RED_THREAD_CORS_ORIGINS` must contain the exact Vercel production origin. See
  [deploy/README.md](deploy/README.md).
- **AI tests:** mocked provider success, invalid credentials, rate limits, retries, timeouts,
  malformed responses, empty responses, length-truncated reasoning, reasoning-only responses,
  citation validation (including combined and plural locators), insufficient evidence, and
  unconfigured-provider behavior.
- **Live AI verification:** DeepSeek V4.1 Flash via TokenHarbor passed the connectivity check for
  `deepseek-v4.1-flash:free`; a live question on the seeded case returned 20 citations, all 20
  validated, `validation_status=validated`, latency about 23.7 s. No API key is stored in the
  repository or reports.
- **Demo integration:** the six synthetic Operation PhishTrace files were uploaded, parsed,
  reconciled, graphed, and reported; the benign control produced no high/medium reconciliation
  anomaly.
- **UI verification:** light and dark themes were exercised in the browser on the dashboard,
  findings, relationship graph, authentication analysis, evidence vault, AI assistant and
  mobile drawer. The selected theme persisted across reloads, the responsive evidence table
  kept its actions usable at 1280 px, and no runtime console errors were observed.
- The configured AI page was also exercised in the browser with a live question and 4/4
  validated citations.

To reproduce:

```bash
cd backend
.venv/bin/pytest -q

cd ../frontend
npm run build
```

---

## Known limitations

- Single-investigator/local-first by default; there is no full multi-user identity system.
- SHA-256 integrity is not a chain-of-custody or pre-acquisition-authenticity proof.
- Timestamp inference can be wrong when logs span a year boundary; the assumption is recorded.
- OCR quality depends on Tesseract, fonts, image quality and language data.
- ELA is skipped for lossless PNG and is only an indicator for JPEG.
- Heuristic temporal proximity is a lead, not a relationship.
- AI responses can be wrong even when citations are structurally valid; human review is required.
- The report's Section 63 section is a draft template, not a legal certificate.
- Live monitoring is optional, disabled by default, and restricted to an explicitly configured
  source.
- The generated demo data is synthetic and must not be presented as real evidence.
- The deployed demo has no user authentication. The frontend, API, evidence, reports and AI
  endpoints are public; use synthetic data only. Do not upload sensitive material.
- Render Free sleeps after inactivity and has 512 MB RAM; Supabase Free projects can pause.
  Open the deployment before a demo and expect a cold-start delay.
- The startup seed recreates the same synthetic case content with new case IDs. Use the
  `scripts/migrate_local_to_cloud.py` migration for the exact local case IDs, audit/AI-query
  history and evidence; it regenerates reports rather than copying old local report files.
- The live Supabase session-pooler and real Cloudflare R2 migration is verified. The Vercel
  frontend still needs the Render API base with `/api` and the exact Vercel origin in Render’s
  `RED_THREAD_CORS_ORIGINS`; see [deploy/README.md](deploy/README.md).

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [AI integration and privacy](docs/AI_INTEGRATION.md)
- [Authentication parser](docs/AUTH_PARSER.md)
- [Demo walkthrough](docs/DEMO.md)
- [Limitations and caveats](docs/LIMITATIONS.md)
- [Windows troubleshooting](docs/WINDOWS.md)

---

**Red Thread does not replace an investigator. It preserves provenance, exposes its reasoning, and
keeps conclusions subject to human review.**
