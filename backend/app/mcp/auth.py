"""Resolve the Bearer token on every MCP request.

Lookup strategy:
1. Hit the in-memory cache. If present and not expired, accept immediately.
2. Cache miss → fetch agents with the same `token_prefix` (cheap, indexed-ish
   via the existing `agents.token_prefix` not-null column) and argon2-verify.
3. On success, cache `(agent_id, is_retired)` for 60 seconds and return.

Retired agents pass argon2 but the tool layer surfaces `AGENT_RETIRED` so they
can't keep predicting.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.lib.tokens import TOKEN_BRAND_PREFIX, TOKEN_PREFIX_LEN, verify_token
from app.mcp.errors import InvalidTokenError
from app.mcp.token_cache import CachedAgent, TokenCache, token_cache


def _looks_like_token(token: str) -> bool:
    return token.startswith(TOKEN_BRAND_PREFIX) and len(token) > TOKEN_PREFIX_LEN


async def resolve_agent(
    db: AsyncSession,
    token: str,
    *,
    cache: TokenCache = token_cache,
) -> Agent:
    """Return the `Agent` for the given Bearer token, or raise `InvalidTokenError`.

    The session is used only on cache miss. On hit we do a single `session.get`
    for the cached agent_id to load the fresh row (so `is_retired` reflects DB
    state if the row was just updated outside this process).
    """
    if not _looks_like_token(token):
        raise InvalidTokenError()

    cached = cache.get(token)
    if cached is not None:
        agent = await db.get(Agent, cached.agent_id)
        if agent is None:
            cache.invalidate_token(token)
            raise InvalidTokenError()
        return agent

    prefix = token[:TOKEN_PREFIX_LEN]
    candidates = (
        await db.scalars(select(Agent).where(Agent.token_prefix == prefix))
    ).all()
    for candidate in candidates:
        if verify_token(token, candidate.token_hash):
            cache.put(token, CachedAgent(agent_id=candidate.id, is_retired=candidate.is_retired))
            return candidate
    raise InvalidTokenError()


def invalidate_agent(agent_id) -> None:  # type: ignore[no-untyped-def]
    """Hook for the REST agent-service to call after rotate/retire."""
    token_cache.invalidate_agent(agent_id)
