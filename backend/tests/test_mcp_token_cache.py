"""TokenCache: TTL + invalidation behavior."""

from __future__ import annotations

import time
from uuid import uuid4

from app.mcp.token_cache import CachedAgent, TokenCache


def test_get_returns_none_when_missing() -> None:
    cache = TokenCache(ttl=60)
    assert cache.get("nope") is None


def test_put_then_get_round_trips() -> None:
    cache = TokenCache(ttl=60)
    agent_id = uuid4()
    cache.put("wca_abc", CachedAgent(agent_id=agent_id, is_retired=False))
    cached = cache.get("wca_abc")
    assert cached is not None
    assert cached.agent_id == agent_id


def test_ttl_expiry_evicts() -> None:
    cache = TokenCache(ttl=0.05)
    cache.put("wca_abc", CachedAgent(agent_id=uuid4(), is_retired=False))
    assert cache.get("wca_abc") is not None
    time.sleep(0.07)
    assert cache.get("wca_abc") is None


def test_invalidate_token_drops_single_entry() -> None:
    cache = TokenCache(ttl=60)
    cache.put("wca_a", CachedAgent(agent_id=uuid4(), is_retired=False))
    cache.put("wca_b", CachedAgent(agent_id=uuid4(), is_retired=False))
    cache.invalidate_token("wca_a")
    assert cache.get("wca_a") is None
    assert cache.get("wca_b") is not None


def test_invalidate_agent_drops_all_entries_for_that_agent() -> None:
    cache = TokenCache(ttl=60)
    rotated = uuid4()
    other = uuid4()
    cache.put("wca_old", CachedAgent(agent_id=rotated, is_retired=False))
    cache.put("wca_other", CachedAgent(agent_id=other, is_retired=False))
    cache.invalidate_agent(rotated)
    assert cache.get("wca_old") is None
    assert cache.get("wca_other") is not None
