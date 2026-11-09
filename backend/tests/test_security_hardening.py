from __future__ import annotations

from app.rate_limit import _client_key, SlidingWindowLimiter
from app.utils.csv_safety import sanitize_csv_cell, sanitize_csv_row


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeURL:
    pass


class _FakeRequest:
    def __init__(self, headers: dict[str, str], host: str = "10.0.0.1") -> None:
        self.headers = headers
        self.client = _FakeClient(host)
        self.url = _FakeURL()


def _settings(hops: int):
    class _S:
        trusted_proxy_hops = hops

    return _S()


def test_forwarded_for_is_ignored_when_no_proxy_is_trusted():
    request = _FakeRequest({"x-forwarded-for": "1.2.3.4"})
    # A client can always set this header itself, so it must not win.
    assert _client_key(request, _settings(0)) == "10.0.0.1"


def test_forwarded_for_uses_the_hop_appended_by_our_proxy():
    request = _FakeRequest({"x-forwarded-for": "1.2.3.4, 203.0.113.9"})
    # The left-most value is attacker supplied; the right-most is ours.
    assert _client_key(request, _settings(1)) == "203.0.113.9"
    assert _client_key(request, _settings(2)) == "1.2.3.4"


def test_forwarded_for_falls_back_to_socket_address():
    request = _FakeRequest({"x-forwarded-for": "garbage"})
    assert _client_key(request, _settings(3)) == "10.0.0.1"


def test_limiter_stays_bounded_under_key_flood():
    limiter = SlidingWindowLimiter()
    limiter.MAX_KEYS = 50
    for index in range(500):
        limiter.hit(f"key-{index}", 5, 60)
    assert len(limiter._events) <= 50


def test_limiter_enforces_the_window():
    limiter = SlidingWindowLimiter()
    for _ in range(3):
        allowed, retry = limiter.hit("k", 3, 60)
        assert allowed
    allowed, retry = limiter.hit("k", 3, 60)
    assert allowed is False
    assert retry >= 1


def test_csv_formula_cells_are_neutralized():
    for payload in ("=cmd|'/c calc'!A0", "+1+1", "-2+3", "@SUM(A1:A2)", "\tTAB", "\rCR"):
        assert sanitize_csv_cell(payload).startswith("'")


def test_csv_plain_values_and_numbers_are_untouched():
    assert sanitize_csv_cell("ordinary text") == "ordinary text"
    assert sanitize_csv_cell("") == ""
    assert sanitize_csv_cell(42) == 42
    assert sanitize_csv_cell(None) is None
    assert sanitize_csv_cell(True) is True


def test_csv_row_sanitization_preserves_keys():
    row = {"username": "=HYPERLINK(\"http://x\")", "count": 3}
    cleaned = sanitize_csv_row(row)
    assert set(cleaned) == {"username", "count"}
    assert cleaned["username"].startswith("'")
    assert cleaned["count"] == 3
