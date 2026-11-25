# Requirements

Complete dependency and software requirements for Red Thread. This is the single place that
answers "what do I need to install, and at what version".

Two things are worth separating, because they fail in different ways:

- **Requirements files** (`backend/requirements*.txt`, `frontend/package.json`) are what you
  actually install. They are the source of truth and are enforced by the build.
- **This document** records the software-level prerequisites and the versions that were verified
  against the current codebase. If this document and a requirements file ever disagree, the
  requirements file wins and this document should be corrected.

---

## 1. Software prerequisites

### Required

| Software | Minimum | Verified with | Notes |
|---|---|---|---|
| Python | 3.11 | 3.14.10 (dev), 3.12 (Docker) | The code uses `X \| None` syntax, so 3.10+ is required |
| Node.js | 20 | 20 LTS or newer | Vite 7 requires Node 20.19+ or 22.12+ |
| npm | 10 | Bundled with Node 20+ | |

### Optional

| Software | Purpose | If absent |
|---|---|---|
| Tesseract OCR | Text extraction from images (`.png`, `.jpg`) | Image uploads still parse; OCR text is skipped with a recorded warning |
| `tesseract-ocr-eng` | English language data for Tesseract | OCR returns no text |
| PostgreSQL 14+ | Production database | SQLite is used locally and works fully |
| Docker | Containerised backend | Not needed for local development |

### Installing the optional software

```bash
# Debian / Ubuntu
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Arch
sudo pacman -S tesseract tesseract-data-eng

# macOS
brew install tesseract

# Windows: use the UB-Mannheim installer, then set the path
#   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

If Tesseract is installed somewhere unusual, point `TESSERACT_CMD` at the binary. The health
endpoint reports whether OCR is available:

```bash
curl http://127.0.0.1:8000/api/health
# "ocr_available": true
```

---

## 2. Backend dependencies

Install from `backend/requirements.txt`. Versions below are the pins in that file, with the
version actually present in the verified environment.

### Core web stack

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `fastapi` | `>=0.115,<1.0` | 0.148.0 | HTTP API, dependency injection, OpenAPI |
| `uvicorn[standard]` | `>=0.30,<1.0` | 0.54.0 | ASGI server |
| `pydantic` | `>=2.8,<3.0` | 2.14.1 | Request/response validation |
| `pydantic-settings` | `>=2.4,<3.0` | 2.16.0 | Environment-driven configuration |
| `python-multipart` | `>=0.0.9` | 0.0.32 | Required by FastAPI for file uploads |

### Persistence

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `SQLAlchemy` | `>=2.0,<3.0` | 2.1.5 | ORM, 2.0-style queries |
| `psycopg[binary]` | `>=3.2,<4.0` | 3.3.6 | PostgreSQL driver (production) |

SQLite support is built into Python; no extra package is needed for local use.

### Analysis and parsing

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `pandas` | `>=2.2,<3.0` | 2.3.3 | Tabular CSV/Excel-style parsing |
| `networkx` | `>=3.3,<4.0` | 3.7 | Graph assembly for the relationship view |
| `python-dateutil` | `>=2.9,<3.0` | 2.9.0 | Flexible timestamp parsing |
| `pdfplumber` | `>=0.11,<1.0` | 0.11.10 | PDF text extraction (invoices) |
| `pypdf` | `>=5.0,<6.0` | 5.9.0 | PDF fallback when pdfplumber is unavailable |

### Reporting

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `reportlab` | `>=4.2,<5.0` | 4.5.1 | PDF report generation |

### Storage

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `boto3` | `>=1.35,<2.0` | 1.43.114 | S3-compatible access to Cloudflare R2 |

### HTTP and authentication

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `httpx` | `>=0.27,<1.0` | 0.28.1 | AI provider calls, test client transport |
| `PyJWT` | `>=2.9,<3.0` | 2.15.1 | Session token signing |
| `google-auth` | `>=2.35,<3.0` | 2.62.1 | Google ID token verification |
| `requests` | `>=2.31,<3.0` | 2.34.2 | Required by `google.auth.transport.requests` |

`requests` is not imported directly by Red Thread, but `google-auth`'s transport layer imports it.
It is therefore a genuine requirement, not a leftover.

### Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Backend development and test dependencies

Install from `backend/requirements-dev.txt`, which includes `requirements.txt`.

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `pytest` | `>=8.3,<9.0` | 8.4.2 | Test runner |
| `pytest-asyncio` | `>=0.24,<1.0` | 0.26.0 | Async test support (mode is `auto`) |
| `respx` | `>=0.21,<1.0` | 0.23.1 | Mock AI provider HTTP calls |

```bash
pip install -r requirements-dev.txt
```

---

## 4. Optional OCR dependencies

Install from `backend/requirements-ocr.txt` only if you need OCR or EXIF processing. Every one of
these imports is guarded, so the application runs without them.

| Package | Pin | Verified | Purpose |
|---|---|---|---|
| `pytesseract` | `>=0.3.13,<1.0` | 0.3.13 | Python wrapper for the Tesseract binary |
| `Pillow` | `>=10.4,<12.0` | 11.3.0 | Image decoding, EXIF GPS extraction |
| `opencv-python-headless` | `>=4.10,<5.0` | 4.14.0.94 | Error Level Analysis for JPEG |

```bash
pip install -r requirements-ocr.txt
```

`opencv-python-headless` is the server variant: it avoids pulling GUI libraries that a headless
host does not have.

> Tesseract is a **system binary**, not a Python package. `pytesseract` alone is not enough; the
> binary must also be installed (see section 1).

---

## 5. Frontend dependencies

Declared in `frontend/package.json` and locked in `frontend/package-lock.json`. Install with
`npm install --include=dev` (the `--include=dev` matters if your environment sets
`NODE_ENV=production`, which skips dev dependencies).

### Runtime

| Package | Version | Purpose |
|---|---|---|
| `react` | `^19.1.0` | UI |
| `react-dom` | `^19.1.0` | DOM renderer |
| `react-router-dom` | `^7.6.0` | Routing and tab deep links |
| `@tanstack/react-query` | `^5.80.0` | Server-state caching |
| `cytoscape` | `^3.32.0` | Relationship graph canvas |
| `leaflet` | `^1.9.4` | Spatial map |
| `react-leaflet` | `^5.0.0` | React bindings for Leaflet |
| `recharts` | `^2.15.0` | Dashboard and analysis charts |
| `lucide-react` | `^0.468.0` | Icon set |
| `date-fns` | `^4.1.0` | Date formatting |
| `@headlessui/react` | `^2.2.0` | Accessible primitives (dialog, menu) |
| `clsx` | `^2.1.1` | Conditional class names |
| `tailwind-merge` | `^2.6.0` | Tailwind class conflict resolution |
| `@types/leaflet` | `^1.9.22` | Type definitions for Leaflet |

### Build and tooling

| Package | Version | Purpose |
|---|---|---|
| `vite` | `^7.0.0` | Dev server and bundler |
| `@vitejs/plugin-react` | `^5.0.0` | React fast refresh |
| `typescript` | `^5.8.0` | Type checking |
| `tailwindcss` | `^3.4.17` | Utility CSS |
| `postcss` | `^8.5.0` | CSS pipeline |
| `autoprefixer` | `^10.4.21` | Vendor prefixes |
| `eslint` | `^10.14.0` | Linting |
| `@eslint/js` | `^10.0.1` | ESLint base config |
| `typescript-eslint` | `^8.72.1` | TypeScript lint rules |
| `eslint-plugin-react-hooks` | `^7.1.1` | Hooks lint rules |
| `eslint-plugin-react-refresh` | `^0.5.7` | Fast-refresh lint rules |

### Testing

| Package | Version | Purpose |
|---|---|---|
| `vitest` | `^5.1.0` | Test runner |
| `jsdom` | `^26.1.0` | Browser environment for tests |
| `@testing-library/react` | `^16.3.0` | Component testing |
| `@testing-library/jest-dom` | `^6.6.3` | DOM matchers |

### Types

| Package | Version |
|---|---|
| `@types/react` | `^19.1.0` |
| `@types/react-dom` | `^19.1.0` |
| `@types/node` | `^26.6.5` |
| `@types/cytoscape` | `^3.21.9` |

### Install

```bash
cd frontend
npm install --include=dev
```

For a reproducible install in CI, use the lockfile:

```bash
npm ci
```

---

## 6. Environment variables

Dependencies have no secrets; configuration does. Copy `backend/.env.example` to `backend/.env`.
Every setting is optional for local development.

The complete list, grouped by concern, is in the main [README](README.md#configuration). The
variables that matter most when installing:

| Variable | Needed for |
|---|---|
| `RED_THREAD_DATABASE_URL` | Using Postgres instead of the default SQLite file |
| `RED_THREAD_STORAGE_BACKEND=r2` + `R2_*` | Storing evidence in Cloudflare R2 |
| `GOOGLE_CLIENT_ID` | Google sign-in (otherwise use the demo workspace) |
| `RED_THREAD_SESSION_SECRET` | Stable sessions across restarts |
| `TESSERACT_CMD` | Tesseract installed outside `PATH` |
| `ISOQUANT_API_KEY` / `COMMANDCODE_API_KEY` / `TOKENHARBOR_API_KEY` | Enabling the AI assistant |

No AI key is needed for the deterministic pipeline, which is the core of the product.

---

## 7. Minimum viable install

The smallest set that runs the full deterministic application, with no OCR and no AI:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install --include=dev
npm run dev
```

That is: Python 3.11+, Node 20+, and the two requirements files. Nothing else is required.

---

## 8. Verifying your environment

```bash
# Versions present
python --version
node --version
npm --version

# Backend imports resolve
cd backend
python -c "import fastapi, sqlalchemy, pandas, networkx, reportlab, httpx, boto3; print('ok')"

# Are the pinned versions satisfied?
# This reads the pins and installed versions without needing extra tools.
python - <<'PY'
import importlib.metadata as md
import re

def spec_ok(spec, have):
    """Minimal check for the >=x,<y form used by this project."""
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    key = tuple(int(n) for n in re.findall(r"\d+", have)[:3])
    for part in parts:
        m = re.match(r"(>=|<=|==|>|<)\s*([\d.]+)", part)
        if not m:
            continue
        op, raw = m.group(1), m.group(2)
        target = tuple(int(n) for n in raw.split("."))
        # Compare on the shared prefix so "2.1.5" vs "3.0" behaves sensibly.
        width = max(len(key), len(target))
        a = key + (0,) * (width - len(key))
        b = target + (0,) * (width - len(target))
        if op == ">=" and not a >= b: return False
        if op == ">"  and not a >  b: return False
        if op == "<=" and not a <= b: return False
        if op == "<"  and not a <  b: return False
        if op == "==" and not a == b: return False
    return True

for line in open("requirements.txt"):
    line = line.strip()
    if not line or line.startswith(("-r", "#")):
        continue
    name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
    spec = line[len(name):].split(";")[0].strip()
    try:
        have = md.version(name)
    except md.PackageNotFoundError:
        print("MISSING", name)
        continue
    print(("OK  " if spec_ok(spec, have) else "FAIL"), name, have, spec)
PY

# Optional software
tesseract --version

# Service health
curl http://127.0.0.1:8000/api/health
```

---

## 9. Known constraints

- **Tesseract is a system binary.** `pip install pytesseract` does not install it. OCR silently
  returns nothing without the binary and its language data.
- **`psycopg[binary]` is only used for Postgres.** Local SQLite needs no driver.
- **`boto3` is only used for R2.** Local storage needs no credentials.
- **`opencv-python-headless` avoids GUI libraries.** Do not swap it for `opencv-python` in a
  container; the full package pulls X11 dependencies and increases image size substantially.
- **Node 20.19+ or 22.12+** is required by Vite 7. Older Node 20 releases fail with an engine
  warning that becomes a hard error.
- **`npm ci` requires the lockfile to be in sync.** If you change `package.json`, run
  `npm install` locally and commit the updated `package-lock.json`.
- **Version pins are ranges, not lockfiles,** on the backend. The verified column records what was
  tested; a fresh install may resolve newer patch versions within the range. For a byte-identical
  environment, generate a lock file with `pip freeze` after installing.

---

## 10. Updating dependencies

```bash
# See what would change, without installing
pip install -r requirements.txt --upgrade --dry-run

# After upgrading, run the full suite before committing
cd backend && .venv/bin/python -m pytest
cd ../frontend && npm test && npm run build && npm run lint
```

Then update the "Verified" column in this document to match what you actually tested. A requirements
document that records versions nobody verified is worse than one that records none.
