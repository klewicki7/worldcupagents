"""MCP tools: get_my_score, get_leaderboard, get_agent_profile.

For M3 the `scores` table is empty (no resolutions yet). These tools query the
real `v_agent_leaderboard` view, so they'll surface zeros/nulls today and real
numbers once M5 lands — no hardcoded shells.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.session import async_session_factory
from app.mcp.context import current_agent
from app.mcp.errors import AgentNotFoundError, InvalidParamError

MAX_LIMIT = 100
DEFAULT_LIMIT = 20

# Direct view query: avoid declaring a SQLAlchemy view class for this small case.
_LEADERBOARD_SQL = text(
    """
    SELECT agent_id, slug, name, model_hint, avatar_url,
           matches_predicted, avg_brier, total_exact_pts
    FROM v_agent_leaderboard
    WHERE matches_predicted >= :min_matches
    ORDER BY avg_brier ASC NULLS LAST,
             total_exact_pts DESC,
             matches_predicted DESC,
             name ASC
    LIMIT :limit OFFSET :offset
    """
)

_RANK_SQL = text(
    """
    WITH ranked AS (
        SELECT agent_id,
               ROW_NUMBER() OVER (
                   ORDER BY avg_brier ASC NULLS LAST,
                            total_exact_pts DESC,
                            matches_predicted DESC,
                            name ASC
               ) AS rank
        FROM v_agent_leaderboard
        WHERE matches_predicted >= :min_matches
    )
    SELECT rank FROM ranked WHERE agent_id = :agent_id
    """
)


def _bound_limit(limit: int) -> int:
    if limit < 1:
        raise InvalidParamError("limit must be ≥ 1", {"field": "limit"})
    return min(limit, MAX_LIMIT)


async def _total_qualified(db: AsyncSession, *, min_matches: int) -> int:
    return (
        await db.scalar(
            text(
                "SELECT COUNT(*) FROM v_agent_leaderboard WHERE matches_predicted >= :m"
            ).bindparams(m=min_matches)
        )
    ) or 0


async def _rank_for(db: AsyncSession, agent_id: UUID, *, min_matches: int) -> int | None:
    row = await db.execute(_RANK_SQL, {"agent_id": agent_id, "min_matches": min_matches})
    found = row.first()
    return int(found[0]) if found is not None else None


async def get_my_score() -> dict[str, Any]:
    """Return your agent's overall standing.

    Empty until matches start resolving (M5+); `matches_predicted=0`,
    `avg_brier=null`, `rank=null` is the legitimate "no data yet" shape.
    """
    agent = current_agent()
    async with async_session_factory() as db:
        # The view excludes retired agents — bypass it for the caller's own row.
        row = (
            await db.execute(
                text(
                    "SELECT COUNT(*), AVG(brier), COALESCE(SUM(exact_score_pts), 0)"
                    " FROM scores WHERE agent_id = :agent_id"
                ),
                {"agent_id": agent.id},
            )
        ).first()
        matches_predicted = int(row[0]) if row and row[0] is not None else 0
        avg_brier = float(row[1]) if row and row[1] is not None else None
        total_exact = int(row[2]) if row else 0
        total = await _total_qualified(db, min_matches=3)
        rank = await _rank_for(db, agent.id, min_matches=3)
        return {
            "agent_id": str(agent.id),
            "name": agent.name,
            "matches_predicted": matches_predicted,
            "avg_brier": avg_brier,
            "total_exact_pts": total_exact,
            "rank": rank,
            "total_agents": total,
        }


async def get_leaderboard(limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict[str, Any]:
    """Public top-N qualified agents.

    Qualification = at least 3 predicted matches (per `docs/05-scoring.md`).
    Returns an empty leaderboard until M5 starts scoring matches.
    """
    current_agent()
    limit = _bound_limit(limit)
    if offset < 0:
        raise InvalidParamError("offset must be ≥ 0", {"field": "offset"})
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                _LEADERBOARD_SQL,
                {"min_matches": 3, "limit": limit, "offset": offset},
            )
        ).all()
        total = await _total_qualified(db, min_matches=3)
        return {
            "total_agents": total,
            "leaderboard": [
                {
                    "rank": offset + idx + 1,
                    "agent_id": str(r.agent_id),
                    "slug": r.slug,
                    "name": r.name,
                    "model_hint": r.model_hint,
                    "matches_predicted": int(r.matches_predicted or 0),
                    "avg_brier": float(r.avg_brier) if r.avg_brier is not None else None,
                    "total_exact_pts": int(r.total_exact_pts or 0),
                }
                for idx, r in enumerate(rows)
            ],
        }


async def get_agent_profile(agent_id_or_slug: str) -> dict[str, Any]:
    """Public profile of any agent. Accepts UUID or slug."""
    current_agent()
    async with async_session_factory() as db:
        agent = await _lookup_agent(db, agent_id_or_slug)
        scores_row = (
            await db.execute(
                text(
                    "SELECT COUNT(*), AVG(brier), COALESCE(SUM(exact_score_pts), 0)"
                    " FROM scores WHERE agent_id = :agent_id"
                ),
                {"agent_id": agent.id},
            )
        ).first()
        matches_predicted = int(scores_row[0]) if scores_row and scores_row[0] is not None else 0
        avg_brier = float(scores_row[1]) if scores_row and scores_row[1] is not None else None
        total_exact = int(scores_row[2]) if scores_row else 0
        rank = await _rank_for(db, agent.id, min_matches=3)
        return {
            "agent_id": str(agent.id),
            "slug": agent.slug,
            "name": agent.name,
            "description": agent.description,
            "model_hint": agent.model_hint,
            "matches_predicted": matches_predicted,
            "avg_brier": avg_brier,
            "total_exact_pts": total_exact,
            "rank": rank,
            "recent_predictions": [],  # M4/M5 will populate
        }


async def _lookup_agent(db: AsyncSession, key: str) -> Agent:
    agent: Agent | None = None
    try:
        agent = await db.get(Agent, UUID(key))
    except ValueError:
        agent = await db.scalar(select(Agent).where(Agent.slug == key))
    if agent is None or agent.is_retired:
        raise AgentNotFoundError(key)
    return agent


# Silence unused-import lints (`desc`/`func` reserved for M5 once aggregates land).
_ = desc, func
