"""Per-agent sliding-window rate limit for MCP tool calls.

60 calls / 60 seconds per agent (per `docs/04-mcp-spec.md` § 7). Sliding-window
deque per agent_id keeps the implementation tiny and bound by `MAX_PER_WINDOW`
entries per agent. Process-local — same caveats as `token_cache`.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from uuid import UUID

MAX_PER_WINDOW = 60
WINDOW_SECONDS = 60.0


class AgentRateLimiter:
    def __init__(self, max_per_window: int = MAX_PER_WINDOW, window: float = WINDOW_SECONDS) -> None:
        self._max = max_per_window
        self._window = window
        self._lock = threading.Lock()
        self._buckets: dict[UUID, deque[float]] = defaultdict(deque)

    def acquire(self, agent_id: UUID) -> bool:
        """Return True if the call is allowed (and recorded), False on limit hit."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._buckets[agent_id]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                return False
            bucket.append(now)
            return True

    def retry_after(self, agent_id: UUID) -> int:
        """Seconds until the oldest entry exits the window; 0 if no bucket."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[agent_id]
            if not bucket:
                return 0
            remaining = (bucket[0] + self._window) - now
            return max(1, int(remaining + 0.999))

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


agent_limiter = AgentRateLimiter()
