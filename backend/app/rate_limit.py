from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from .config import Settings, get_settings

_DEMO_PATH = "/api/auth/demo"
_GOOGLE_PATH = "/api/auth/google"
_AI_PREFIX = "/api/ai"
_REPORT_WRITE_SUFFIX = "/reports"
_EVIDENCE_WRITE_SUFFIX = "/evidence"
_SKIP_PREFIXES = ("/api/health", "/docs", "/redoc", "/openapi.json")


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])) + 1)
                return False, retry_after
            events.append(now)
            return True, 0


limiter = SlidingWindowLimiter()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _session_key(request: Request) -> str:
    token = request.cookies.get("red_thread_session", "")
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    return token or _client_key(request)


def _limit_for(request: Request, settings: Settings) -> tuple[int, int, str]:
    path = request.url.path
    method = request.method.upper()
    if path == _DEMO_PATH:
        return settings.rate_limit_demo_per_10_minutes, 600, "demo"
    if path == _GOOGLE_PATH:
        return settings.rate_limit_auth_per_minute, 60, "auth"
    if path.startswith(_AI_PREFIX):
        return settings.rate_limit_ai_per_minute, 60, "ai"
    if method == "POST" and path.endswith(_REPORT_WRITE_SUFFIX):
        return 5, 300, "reports"
    if method == "POST" and _EVIDENCE_WRITE_SUFFIX in path:
        return settings.rate_limit_uploads_per_minute, 60, "uploads"
    return settings.rate_limit_api_per_minute, 60, "api"


def rate_limit_request(request: Request) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    if not request.url.path.startswith("/api"):
        return
    if request.url.path.startswith(_SKIP_PREFIXES):
        return
    if request.method.upper() == "OPTIONS":
        return

    limit, window, scope = _limit_for(request, settings)
    identity = _client_key(request) if scope in {"demo", "auth"} else _session_key(request)
    key = f"{scope}:{identity}"
    allowed, retry_after = limiter.hit(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit reached. Please retry shortly.",
            headers={"Retry-After": str(retry_after)},
        )
