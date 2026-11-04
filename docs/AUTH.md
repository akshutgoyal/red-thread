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
