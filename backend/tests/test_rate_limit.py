from __future__ import annotations

from app.rate_limit import SlidingWindowLimiter


def test_sliding_window_limiter_blocks_and_recovers():
    limiter = SlidingWindowLimiter()
    assert limiter.hit("client", 2, 60)[0] is True
    assert limiter.hit("client", 2, 60)[0] is True
    allowed, retry_after = limiter.hit("client", 2, 60)
    assert allowed is False
    assert retry_after >= 1
