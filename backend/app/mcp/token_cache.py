"""In-memory TTL cache for argon2 token verifications.

Argon2 verify is intentionally expensive (~50–100ms). At 60 calls/min/agent the
hot path needs sub-ms lookups, so after the first successful verify we cache
`sha256(token) → (agent_id, expires_at)` for `TOKEN_CACHE_TTL` seconds. The cache
is process-local; with the single-Fly-machine v1 deploy that's fine. Move to
Redis if/when we scale horizontally (per TRD § 6).
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from uuid import UUID

TOKEN_CACHE_TTL = 60.0  # seconds


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CachedAgent:
    agent_id: UUID
    is_retired: bool


class TokenCache:
    def __init__(self, ttl: float = TOKEN_CACHE_TTL) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[CachedAgent, float]] = {}

    def get(self, token: str) -> CachedAgent | None:
        fp = fingerprint(token)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(fp)
            if entry is None:
                return None
            cached, expires_at = entry
            if expires_at <= now:
                self._entries.pop(fp, None)
                return None
            return cached

    def put(self, token: str, cached: CachedAgent) -> None:
        fp = fingerprint(token)
        with self._lock:
            self._entries[fp] = (cached, time.monotonic() + self._ttl)

    def invalidate_token(self, token: str) -> None:
        with self._lock:
            self._entries.pop(fingerprint(token), None)

    def invalidate_agent(self, agent_id: UUID) -> None:
        """Drop every cached entry for `agent_id` (used on rotation/retirement)."""
        with self._lock:
            stale = [fp for fp, (cached, _) in self._entries.items() if cached.agent_id == agent_id]
            for fp in stale:
                self._entries.pop(fp, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


token_cache = TokenCache()
