# Authentication Parser

The supplied `auth_parser.py` was inspected and integrated rather than replaced. Its reusable
logic now lives in `backend/app/parsers/auth_log_parser.py`; the FastAPI pipeline uses
`backend/app/parsers/auth_adapter.py`.

## Preserved capabilities

- SSH accepted and failed logins.
- SSH session opened/closed events.
- Sudo command events.
- Failed-login burst detection.
- Persistent failed-login detection.
- Multiple targeted usernames.
- Invalid username detection.
- Suspicion scoring.
- JSON export.
- CSV export.
- Optional live monitoring.

Default thresholds:

- Burst: **8 failed logins within 60 seconds**.
- Persistent: **10 failed logins within 15 minutes**.
- Multiple usernames: 5 distinct usernames within the persistent window.
- Invalid users: 2 invalid-user failures within the persistent window.

All thresholds are configurable through `AuthParserConfig` and CLI flags.

## Corrections made during integration

| Issue | Correction |
|---|---|
| Hardcoded year `2000` | Missing years are inferred from the case/reference date; the raw timestamp, inferred year and basis are recorded. `--year` fixes the year explicitly. |
| CLI parsing executed on import | Moved into `main(argv=None)` and `if __name__ == "__main__"`; importing the module is side-effect free. |
| IPv4-only extraction | IPv4 and IPv6 are validated and canonicalized with `ipaddress`. |
| No source line tracking | Every event stores its source line number and raw line. |
| Batch/live divergence | Both use the same `LiveSecurityTracker` and `evaluate_ip` engine. |
| Duplicate/incremental reasons | Batch consolidation keeps the final, most complete reason per rule. |
| Malformed lines silently dropped | Preserved as bounded parse warnings with line numbers. |
| No raw timestamp | `timestamp_raw` is retained alongside the normalized UTC value. |
| Unsafe live exit | Live monitoring uses a stop event/`sys.exit` and does not call a site-specific `exit()`. |

## Timestamp handling

Syslog timestamps usually look like `Oct 15 06:00:00` and contain no year or timezone.

Red Thread records:

- The raw timestamp.
- The normalized UTC timestamp when possible.
- `timestamp_confidence`: `exact`, `inferred_year`, `ambiguous`, or `unknown`.
- A warning describing the inferred year and assumed timezone.

The year is chosen from an explicit `--year`, or from the case/upload reference date using the
closest non-future candidate year. This is an inference, not a source fact. If the log spans a
year boundary, verify the year against the source system.

The default auth timezone is `UTC` (`RED_THREAD_AUTH_DEFAULT_TIMEZONE`). Financial/call/chat
evidence uses `RED_THREAD_DEFAULT_TIMEZONE`, default `Asia/Kolkata`.

## Batch and live behavior

Batch parsing:

1. Reads lines in order.
2. Parses supported lines and records warnings for unknown lines.
3. Feeds events into the shared tracker in timestamp order.
4. Consolidates incremental alerts per source IP.

Live monitoring:

1. Tails the configured log (by default from the end; `--from-start` reads existing lines).
2. Parses complete lines, handles partial writes and truncation.
3. Emits an alert when the score increases or a new rule appears.
4. Can invoke callbacks for API persistence.

Exact batch/live parity is tested for the same event sequence.

## CLI

```bash
cd backend

# Batch parse with JSON and CSV exports
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log \
    --year 2026 \
    --json auth.json \
    --csv auth_events.csv

# Configurable thresholds
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log \
    --burst-limit 5 --burst-window 30 \
    --persistent-limit 8 --persistent-window 600

# Live monitoring from the current end of the file
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log --live

# Live monitoring including existing lines
.venv/bin/python -m app.parsers.auth_log_parser /path/to/auth.log --live --from-start
```

## Live monitoring scope

The CLI is the supported live-monitoring path. The web API intentionally does not expose a
start/stop endpoint for arbitrary paths. `RED_THREAD_ENABLE_LIVE_MONITOR` is a reserved guard for a
future authorized integration; it does not grant access by itself. Point the CLI only at an
authorized log source and account for log rotation, permissions, and retention policy.

## Unified output

The adapter converts each parsed event into a canonical event with:

- `event_type` (`auth.login`, `auth.session`, `auth.sudo`, `auth.invalid_user`,
  `auth.connection_closed`, `auth.disconnect`)
- raw and normalized timestamps
- source IP, username, host, authentication result/method
- PID, port, session event, sudo target user/command
- source line number and raw snippet
- warnings and parser metadata

Authentication alerts become findings with:

- category `authentication`
- detection method `deterministic_rule`
- severity mapped from the score level
- rule IDs and human-readable reasons
- limitations and alternative explanations
- links to the exact source events

## What the parser does not claim

A failed-login burst may be benign user error, stale credentials, a scanner, shared NAT, or
authorized testing. A successful login after failures may be legitimate. The parser reports
indicators for human review, not proof of compromise.
