"""Web security primitives: response headers + a login brute-force limiter.

Single-instance MVP scope. Phase 2 should move the limiter to a shared store
and add synchronizer-token CSRF; Phase 1 relies on SameSite=Strict cookies,
which browsers refuse to attach to any cross-site request (incl. htmx POSTs).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware

# Everything is self-hosted (htmx vendored, styles local), so 'self' is enough.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attaches hardening headers to every response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response


class LoginRateLimiter:
    """Fixed-window per-key limiter. In-memory — single instance only."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 300) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        return hits

    def is_blocked(self, key: str) -> bool:
        return len(self._prune(key, time.monotonic())) >= self._max

    def register_failure(self, key: str) -> None:
        self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
