# Authentication and workspace access

Red Thread can require a signed-in session while keeping the synthetic demo
available to evaluators.

## Access model

- **Google user:** sees only cases they own. A new Google account starts with an
  empty case list; investigation navigation remains disabled until the first
  case is created.
- **Demo principal:** the **Explore demo** button issues a demo session with full
  case permissions. Demo cases are shared synthetic records.
- The existing seeded cases are marked as demo cases by the startup migration
  and seed service.
- API case routes enforce ownership. A DEMO session can access only demo cases;
  a Google user can access only their own cases.

## Google setup

1. Create a Google Cloud project and an OAuth 2.0 **Web application** client.
2. Add authorized JavaScript origins:
   - `http://localhost:5173`
   - `https://red-thread-virid.vercel.app`
3. Set the same public client ID in both environments:
   - Backend/Render: `GOOGLE_CLIENT_ID`
   - Frontend/Vercel: `VITE_GOOGLE_CLIENT_ID`
4. Set a long random backend session secret:
   - `RED_THREAD_SESSION_SECRET`
5. Keep `RED_THREAD_AUTH_REQUIRED=true` in deployed environments.

The frontend uses Google Identity Services and sends the Google ID token to
`POST /api/auth/google`. The backend verifies the token and issues a signed
Red Thread session token. No Google client secret is required.

## Local demo without Google

The **Explore demo workspace** button does not require Google credentials. This
is the intended local fallback when `VITE_GOOGLE_CLIENT_ID` is not configured.

## API behaviour

- `POST /api/auth/google` — exchange a Google ID token for a Red Thread session.
- `POST /api/auth/demo` — issue a demo session.
- `GET /api/auth/me` — validate the current session.
- All case-scoped API routes require a session when
  `RED_THREAD_AUTH_REQUIRED=true`.
- Case access is checked from the path, `case_id` query parameter, or
  `X-Case-ID` header.
- `/api/health`, `/api/auth/*`, `/docs` and `/openapi.json` remain public.

## Seed repair

The startup demo seeder now detects incomplete demo cases. It preserves
complete evidence and review/annotation history, uploads missing evidence, and
re-parses evidence left in `uploaded` or failed states. It does not touch other
cases.


## Session security

Sessions are stored in an **HttpOnly, SameSite cookie**. The browser never
reads the session token. Cross-site production cookies are set with
`SameSite=None; Secure`; local HTTP development uses `SameSite=Lax`.

## Rate limits

The API applies in-memory sliding-window limits per IP/session:

- demo login: 3 per 10 minutes per IP
- Google login: 10 per minute per IP
- AI: 8 per minute per session/IP
- report generation: 5 per 5 minutes
- evidence uploads: 30 per minute
- general API: 120 per minute

Set `RED_THREAD_RATE_LIMIT_ENABLED=false` only for local testing. A multi-instance
deployment should replace the in-memory limiter with a shared store.

## AI budget

`RED_THREAD_AI_BUDGET_USD` defaults to **0.50**. AI requests are rejected with
HTTP 402 once recorded Isoquant usage reaches that estimated spend. This is an
application-side budget guard; it is separate from the provider account
balance, which should also be capped in the Isoquant console.

## Shared demo workspace

The demo is one shared synthetic workspace composed of ownerless demo cases.
All demo visitors see and can edit the same demo data, as requested. Demo
sessions are full-permission synthetic sessions.

Old visitor-owned demo copies created by the previous experimental
per-visitor implementation are hidden from the shared demo and removed after
`DEMO_COPY_TTL_HOURS` (default 24) by startup cleanup, including their R2
objects.

## Session persistence

Sessions use a persistent HttpOnly cookie with both `Max-Age` and `Expires`
(seven days by default). The frontend calls `/auth/me` on load and retries
transient failures once before showing the login screen, so a page refresh or
new tab keeps a valid Google session.

## Security hardening

The following controls protect the session and the API surface. They are covered by
`backend/tests/test_security_hardening.py` and `backend/tests/test_session_auth.py`.

| Control | Behaviour |
|---|---|
| Session transport | The session JWT is set only in an `HttpOnly`, `Secure` (in production), `SameSite=None` cookie. The login response contains no token, so page scripts and XSS payloads cannot read it. |
| CSRF | `SameSite=None` provides no CSRF protection, so state-changing requests are checked against the `CORS_ORIGINS` allow-list using the `Origin` header. Cross-site writes receive `403 Cross-site request blocked.` |
| Rate-limit identity | `X-Forwarded-For` is attacker-controlled. Only the entries appended by our own proxies are trusted, controlled by `RED_THREAD_TRUSTED_PROXY_HOPS`. Limiter keys are hashed and the table is capped so an identity flood cannot exhaust memory. |
| Security headers | API responses set `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cross-Origin-Resource-Policy`, `Permissions-Policy`, a locked-down `Content-Security-Policy`, and HSTS over HTTPS. |
| Uploaded content | Served with `nosniff`, a sandboxing CSP and `Content-Disposition`, so a stored file cannot execute in the app origin. |
| CSV export | Cells beginning with `=`, `+`, `-`, `@`, tab, CR or NUL are prefixed with a single quote to neutralize spreadsheet formula injection. |
| Startup guard | The backend refuses to start with `RED_THREAD_ENVIRONMENT=production` when `RED_THREAD_SESSION_SECRET` is the shipped placeholder or shorter than 32 characters. |
| API docs | `/docs`, `/redoc` and `/openapi.json` are disabled in production unless `RED_THREAD_EXPOSE_API_DOCS=true`. |

### Column mapping

Generic CSV, JSON and JSONL files can be mapped explicitly when the parser's alias
detection does not recognize the headers:

- `GET /api/evidence/{id}/mapping` returns the headers, canonical fields, a suggested
  mapping and up to five sample rows.
- `PUT /api/evidence/{id}/mapping` stores the confirmed mapping in
  `Evidence.metadata_json["column_mapping"]`. A timestamp column is required.
- Parsing then reads the mapped columns. The stored bytes are never modified; reparse to
  rebuild events.
