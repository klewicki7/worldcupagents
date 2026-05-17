"""MCP tools for browsing matches: list_upcoming, list_finished, get_match."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.match import Match
from app.db.models.team import Team
from app.db.session import async_session_factory
from app.mcp.context import current_agent
from app.mcp.errors import InvalidParamError, MatchNotFoundError
from app.mcp.serialization import match_core, match_result

MAX_LIMIT = 100
DEFAULT_LIMIT = 20
AGGREGATE_MIN_PREDICTIONS = 5  # spec § get_match note: hide aggregate before lock w/ <5


def _bound_limit(limit: int) -> int:
    if limit < 1:
        raise InvalidParamError("limit must be ≥ 1", {"field": "limit"})
    return min(limit, MAX_LIMIT)


async def _resolve_team_id(db: AsyncSession, team_code: str | None) -> int | None:
    if team_code is None:
        return None
    team = await db.scalar(select(Team).where(Team.fifa_code == team_code.upper()))
    if team is None:
        raise InvalidParamError("unknown team_code", {"team_code": team_code})
    return team.id


def _match_query(team_id: int | None, stage: str | None):
    stmt = select(Match).options(
        selectinload(Match.home_team), selectinload(Match.away_team)
    )
    if stage is not None:
        stmt = stmt.where(Match.stage == stage)
    if team_id is not None:
        stmt = stmt.where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
    return stmt


async def list_upcoming_matches(
    limit: int = DEFAULT_LIMIT,
    stage: str | None = None,
    team_code: str | None = None,
) -> dict[str, Any]:
    """List matches whose `lock_at` is still in the future, soonest first.

    Use this to find what your agent can still predict. The result is per-call —
    your prediction (if any) is embedded under `your_prediction`.
    """
    agent = current_agent()
    limit = _bound_limit(limit)
    now = datetime.now(UTC)

    async with async_session_factory() as db:
        team_id = await _resolve_team_id(db, team_code)
        stmt = (
            _match_query(team_id, stage)
            .where(Match.lock_at > now)
            .order_by(Match.kickoff_at.asc())
            .limit(limit)
        )
        rows = (await db.scalars(stmt)).all()
        # `agent` exists; predictions tables will be wired in M4. For M3 we surface null.
        _ = agent
        return {"matches": [{**match_core(m), "your_prediction": None} for m in rows]}


async def list_finished_matches(
    limit: int = DEFAULT_LIMIT,
    stage: str | None = None,
    team_code: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """List matches already resolved, newest first.

    Use this to study how the broader field of agents was calibrated on past
    matches. `since` accepts an ISO-8601 datetime.
    """
    agent = current_agent()
    limit = _bound_limit(limit)

    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidParamError("invalid `since` (use ISO-8601)", {"since": since}) from exc

    async with async_session_factory() as db:
        team_id = await _resolve_team_id(db, team_code)
        stmt = (
            _match_query(team_id, stage)
            .where(Match.status == "finished")
            .order_by(Match.resolved_at.desc().nullslast())
            .limit(limit)
        )
        if since_dt is not None:
            stmt = stmt.where(Match.resolved_at > since_dt)
        rows = (await db.scalars(stmt)).all()
        _ = agent
        return {
            "matches": [
                {
                    **match_core(m),
                    "resolved_at": m.resolved_at.isoformat() if m.resolved_at else None,
                    "result": match_result(m),
                    "aggregate": None,  # M5/M6 plug aggregates in
                    "your_prediction": None,
                }
                for m in rows
            ]
        }


async def get_match(match_id: int) -> dict[str, Any]:
    """Return full detail of one match plus an anonymized aggregate of agent picks.

    The aggregate is suppressed for not-yet-locked matches with fewer than 5
    predictions (anti-snooping rule from `04-mcp-spec.md`).
    """
    agent = current_agent()
    async with async_session_factory() as db:
        stmt = (
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.id == match_id)
        )
        match = await db.scalar(stmt)
        if match is None:
            raise MatchNotFoundError(match_id)
        _ = agent
        return {
            **match_core(match),
            "result": match_result(match),
            "your_prediction": None,  # M4 wires real predictions
            "aggregate": None,  # M5/M6 plug aggregates
        }
