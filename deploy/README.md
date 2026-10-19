# Deploying Red Thread: Vercel + Render + Supabase + Cloudflare R2

This is the managed free-tier deployment:

```text
Browser
  └─> Vercel (React frontend)
        └─> Render (FastAPI API, Docker, Tesseract)
              ├─> Supabase Postgres (cases, evidence metadata, events, findings, audit)
              ├─> Cloudflare R2 (evidence files and generated reports)
              └─> TokenHarbor / CommandCode (optional AI)
```

The API is stateless. Render’s ephemeral filesystem is not used for persisted data.
Supabase and R2 retain everything across Render restarts and redeploys.

## 0. Get the repository

The code is published at <https://github.com/akshutgoyal/red-thread>. Clone it:

```bash
git clone https://github.com/akshutgoyal/red-thread.git
cd red-thread
```

`.env`, `data/`, `reports/`, `node_modules/` and build outputs are gitignored. Do not commit
API keys, the database, or the local evidence/report directories.

## Free-tier limits to expect

- **Vercel Hobby:** static frontend; check Vercel’s current non-commercial terms.
- **Render Free:** 512 MB RAM and sleep after inactivity. The first request after a
  cold start can take up to a minute. No persistent disk; this deployment does not need one.
- **Supabase Free:** small Postgres database. A project may pause after a period of
  inactivity; wake it in the Supabase dashboard before a demo.
- **Cloudflare R2 Free:** currently 10 GB-month storage, 1 million Class A and 10 million
  Class B operations, with no egress fees. The demo data is under 1 MB.
- The two demo cases are recreated by an idempotent startup seed. This deployment does
  **not** migrate the exact local case IDs, AI-query history or audit history. It recreates
  the same synthetic PhishTrace and benign-control content with new IDs.

## 1. Supabase Postgres

1. Create a Supabase project and wait for the database to become ready.
2. Open **Project Settings → Database → Connection string**.
3. Choose the **Session pooler** (IPv4). Copy the URI. It looks like:

   ```text
   postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

4. Add `?sslmode=require` if it is not already present.
5. Use that value as `RED_THREAD_DATABASE_URL`.

The app accepts `postgresql://` and converts it to the installed `psycopg` driver.
If the password contains special characters, copy Supabase’s already-encoded URI.
Tables are created automatically on first startup; there is no migration step.

The app uses the session pooler and sets `pool_pre_ping` and `prepare_threshold=None`.
If you use the transaction pooler instead, keep the session pooler recommendation unless
you have verified transaction-pooler behavior with the app.

## 2. Cloudflare R2

1. In the Cloudflare dashboard, open **R2** and create a private bucket, for example
   `red-thread-evidence`.
2. Open **Manage R2 API Tokens → Create API token**.
3. Grant **Object Read & Write** and restrict it to that bucket.
4. Copy:
   - Access Key ID
   - Secret Access Key
   - Account ID
5. Keep the bucket private. The backend proxies evidence and report downloads through
   the authenticated API, so R2 CORS is not required.

Object layout:

```text
evidence/<case_id>/<stored_filename>
reports/<case_id>/<report_filename>
```

## 3. Render backend

The repository includes `Dockerfile`, `.dockerignore` and `render.yaml`.

### Option A: Render Blueprint

1. In Render, create a **New Blueprint** and connect this repository.
2. Render reads `render.yaml`. It creates a Docker web service named `red-thread-api`
   on the free plan with health check `/api/health`.
3. Enter the secret values when prompted.

### Option B: Manual web service

1. **New → Web Service**, connect the repository.
2. Runtime: **Docker**.
3. Dockerfile path: `./Dockerfile`; context: `.`.
4. Plan: **Free**; health check path: `/api/health`.
5. Add the environment variables below.

### Render environment variables

| Variable | Value |
|---|---|
| `RED_THREAD_ENVIRONMENT` | `production` |
| `RED_THREAD_STORAGE_BACKEND` | `r2` |
| `RED_THREAD_SEED_DEMO` | `true` |
| `RED_THREAD_DATABASE_URL` | Supabase session-pooler URI with `?sslmode=require` |
| `RED_THREAD_CORS_ORIGINS` | Exact Vercel origin, e.g. `https://red-thread-virid.vercel.app` (trailing slash is normalized) |
| `TOKENHARBOR_API_KEY` | Your TokenHarbor key (or set `COMMANDCODE_API_KEY`) |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret |
| `R2_BUCKET` | `red-thread-evidence` (your bucket name) |
| `RED_THREAD_AI_PROVIDER` | `auto`, `tokenharbor`, `commandcode`, or `none` |
| `RED_THREAD_AI_MAX_TOKENS` | `16384` |
| `RED_THREAD_DEFAULT_TIMEZONE` | `Asia/Kolkata` |
| `RED_THREAD_AUTH_DEFAULT_TIMEZONE` | `UTC` |
| `RED_THREAD_ENABLE_LIVE_MONITOR` | `false` |
| `RED_THREAD_MAX_UPLOAD_MB` | `50` |

`RED_THREAD_AI_PROVIDER=auto` prefers `COMMANDCODE_API_KEY`, then `TOKENHARBOR_API_KEY`.
Set an explicit provider to avoid ambiguity. The AI key stays server-side and is never
sent to Vercel or returned by the API.

The Docker image installs `tesseract-ocr` and `tesseract-ocr-eng`, so image OCR works on
Render. The container runs as a non-root user and listens on Render’s `$PORT`.

## 4. Vercel frontend

1. **New Project**, import the repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Vite**. Build command `npm run build`; output directory `dist`.
   The included `frontend/vercel.json` adds the SPA rewrite.
4. Add environment variables:

   | Variable | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://<your-render-service>.onrender.com/api` |

   No trailing slash is required; the client normalizes it.
5. Deploy.
6. Copy the Vercel production URL into Render’s `RED_THREAD_CORS_ORIGINS`, then restart or
   redeploy the Render service so the CORS setting is loaded.
7. If you use a custom domain, add that exact origin to `RED_THREAD_CORS_ORIGINS` as a
   comma-separated list and keep the Vercel origin too.

Vercel bakes `VITE_API_BASE_URL` into the build. If the Render URL changes, update the
Vercel variable and redeploy the frontend.

## 5. First boot and demo seed

On the first Render startup with `RED_THREAD_SEED_DEMO=true`, the backend:

1. Creates the Supabase tables.
2. Creates the two synthetic cases if their exact titles are not already present.
3. Uploads the sample evidence to R2.
4. Runs the deterministic parsers and reconciliation.

Expected result:

| Case | Evidence | Events | Findings |
|---|---:|---:|---:|
| Operation PhishTrace (Synthetic Demo) | 6 | 69 | 17 |
| Benign Control (Synthetic Demo) | 2 | 3 | 4 |

The operation case is created last and therefore appears first in the case list. The seed
is idempotent by case title: later restarts do not duplicate it.

The seed runs before the server accepts requests. On Render Free it can take a couple of
minutes because of the PDF/image parsing and OCR. Watch the Render logs for
`Demo seed result`.

### Clean re-seed (destructive, synthetic demo only)

If a seed was partially created and you want to start clean:

1. In the Supabase SQL editor, delete only the two synthetic cases:

   ```sql
   delete from cases
   where title in (
     'Operation PhishTrace (Synthetic Demo)',
     'Benign Control (Synthetic Demo)'
   );
   ```

   The schema uses cascading deletes for case-owned records. Confirm the cascade
   behavior before running this in a database with any non-demo data.
2. Delete the matching `evidence/<case_id>/` and `reports/<case_id>/` prefixes in R2.
3. Restart the Render service.

Do not delete the Supabase project or the R2 bucket unless you intend to lose all data.

### 5b. Migrate the exact local cases (optional)

The startup seed recreates the synthetic content with new case IDs. To copy the exact current
local cases into Supabase and R2 instead, use the migration script.

1. Create the cloud credential file. It is gitignored:

   ```bash
   cp backend/.env.example backend/.env.cloud
   ```

2. Put the cloud values in `backend/.env.cloud`:

   ```text
   RED_THREAD_DATABASE_URL="postgresql://postgres.smtjnyniedtorzwghqpk:<password>@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
   RED_THREAD_STORAGE_BACKEND=r2
   R2_ACCOUNT_ID=<cloudflare-account-id>
   R2_ACCESS_KEY_ID=<r2-access-key-id>
   R2_SECRET_ACCESS_KEY=<r2-secret-access-key>
   R2_BUCKET=red-thread-evidence
   ```

   Leave `R2_ENDPOINT` unset for Cloudflare; the app derives
   `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`. The password is the Supabase
   database password, not the anon/service-role key. Do not commit this file.

3. Run the migration from the project root:

   ```bash
   backend/.venv/bin/python scripts/migrate_local_to_cloud.py \
     --env-file backend/.env.cloud --replace
   ```

   `--replace` removes remote seed cases with the same demo titles but different IDs, plus
   their R2 prefixes. Cases that already have the local IDs are kept. The script skips tables
   that are already fully copied, resumes missing tables, and generates only missing reports,
   so it is safe to re-run after an interrupted migration. It never removes unrelated cases.

4. What the script does:
   - Copies all records in `data/red-thread.db`: cases, evidence metadata, events, entities,
     event links, findings, finding links, graph edges, audit events and AI queries.
   - Uploads the local evidence bytes to R2 under `evidence/<case_id>/<filename>`.
   - Generates fresh Red Thread PDF and JSON reports from the migrated data. Old local report
     files are not uploaded.
   - Preserves the exact local case IDs `78bb46f55b3c4e8c96c6ed972f6db583` and
     `87c31261e9524693b5cad74ebca19394`.

   The verified local counts are 2 cases, 8 evidence files, 72 events, 21 findings, 10 AI
   queries, 41 audit events and 60 graph edges. The migration generates 4 new reports.

5. To make the local backend use Supabase/R2 instead of SQLite/local files, put the same
   variables in `backend/.env` and restart the backend. Keep `backend/.env.cloud` only for the
   one-time migration if you want local development to stay on SQLite.

6. The Render service can keep `RED_THREAD_SEED_DEMO=true`. The seed is idempotent by case
   title and will skip the migrated cases.

The migration does not copy the local SQLite file itself, local venvs, or the old local report
PDFs. The local database and evidence remain as a backup.

## 6. Public access

The deployed demo has **no login, access code or user authentication**. The frontend, API,
evidence, reports, audit data and AI endpoints are public. Use synthetic evidence only and never
upload sensitive or real case material to a public URL.

CORS is controlled by `RED_THREAD_CORS_ORIGINS`. Trailing slashes are normalized, so
`https://red-thread-virid.vercel.app/` is treated as
`https://red-thread-virid.vercel.app`. Use the exact origin with no path.

## 7. Verification

```bash
# Health should report database=ok, ocr_available=true, and the configured AI provider.
curl -s https://<render-service>.onrender.com/api/health

# This should return the two cases without any authentication header.
curl -s https://<render-service>.onrender.com/api/cases
```

In the browser:

1. Open the Vercel URL.
2. Confirm the active case is **Operation PhishTrace (Synthetic Demo)**.
3. Open **Evidence vault**, open `payment_screenshot.png`, and confirm the preview loads.
4. Run **Verify** on an evidence row and confirm the SHA-256 matches.
5. Open **Reports**, generate JSON or PDF, and download it.
6. Open **AI assistant** and ask a grounded question such as:
   “Which evidence supports the amount discrepancy, and what are the limitations?”
   The first request may be slow on the free tier. A response with validated citations is
   AI-generated interpretation, not proof.

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| Render deploy fails or the service is unhealthy | Render build/runtime logs; Supabase URI; R2 credentials; `/api/health`. |
| `database=error` | Supabase project paused or unreachable; use the Session pooler URI and `sslmode=require`; wake the project. |
| No cases after startup | `RED_THREAD_SEED_DEMO=true`; Render logs for `Demo seed result`; Supabase and R2 permissions. |
| Seed fails on OCR or memory | Render Free has 512 MB. Retry after the deploy settles; if it consistently fails, use a larger Render instance or pre-seed from a machine with the same Supabase/R2 configuration. |
| CORS error | `RED_THREAD_CORS_ORIGINS` must contain the exact browser origin; trailing slashes are normalized. Restart Render after changing it. Check the `OPTIONS` preflight returns `access-control-allow-origin`. |
| AI disabled | Set `TOKENHARBOR_API_KEY` or `COMMANDCODE_API_KEY`; check `/api/ai/status` and the AI page banner. |
| AI empty/truncated answer | Keep `RED_THREAD_AI_MAX_TOKENS=16384`; lower `RED_THREAD_AI_MAX_CONTEXT_CHARS` if the provider limit is smaller. |
| Supabase free project paused | Unpause it in the Supabase dashboard; the first request may fail until it wakes. |
| R2 `AccessDenied` | The token must have Object Read & Write on the exact bucket; verify account ID, key, secret and bucket name. |
| First request takes ~1 minute | Render Free slept after inactivity. Retry if the first request fails. |

## 9. What is and is not migrated

- **Migrated by the startup seed:** the same synthetic PhishTrace and benign-control evidence
  content, deterministic events, findings, entities, relationships and reports generated after
  deployment. It uses new case IDs.
- **Exact local snapshot:** use the migration script in 5b. It copies the exact local case IDs,
  records, audit/AI-query history and evidence, and regenerates Red Thread reports.
- **Not copied by the migration:** the SQLite file itself, local venvs, and old local report
  files. The local `data/` and `reports/` directories are gitignored and are not part of the
  Docker image.
- Never put SQLite on R2; the migration writes rows to Supabase and objects to R2.

## 10. Security and privacy

- Keep `TOKENHARBOR_API_KEY` / `COMMANDCODE_API_KEY` in Render’s secret store only.
- Never commit `.env`; the repository only contains `.env.example`.
- Keep the R2 bucket private.
- The deployed demo has no authentication. Do not upload real or sensitive evidence to the
  public demo URL.
- AI requests send selected case excerpts to the configured provider. Review the provider’s
  data-handling terms before using confidential material.
- Reports are marked draft-only for human review and are not automatically court-admissible.
  Red Thread does not sign or attest a Section 63 BSA certificate.
