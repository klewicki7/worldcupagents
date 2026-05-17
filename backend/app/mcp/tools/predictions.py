"""MCP tools: get_my_predictions (read) + submit_prediction (write)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.match import Match
from app.db.models.prediction import Prediction
from app.db.session import async_session_factory
from app.domain.prediction_service import submit_prediction as service_submit_prediction
from app.mcp.context import current_agent
from app.mcp.errors import InvalidParamError

MAX_LIMIT = 100
DEFAULT_LIMIT = 20


def _bound_limit(limit: int) -> int:
    if limit < 1:
        raise InvalidParamError("limit must be ≥ 1", {"field": "limit"})
    return min(limit, MAX_LIMIT)


def _summary(match: Match) -> str:
    home = match.home_team.name_en if match.home_team else match.home_placeholder or "TBD"
    away = match.away_team.name_en if match.away_team else match.away_placeholder or "TBD"
    group = f" (Group {match.group_letter}" if match.group_letter else f" ({match.stage}"
    return f"{home} vs {away}{group}, {match.kickoff_at.date().isoformat()})"


async def _fetch(
    db: AsyncSession,
    *,
    agent_id,  # type: ignore[no-untyped-def]
    limit: int,
    only_open: bool,
    only_finished: bool,
) -> list[dict[str, Any]]:
    stmt = (
        select(Prediction)
        .where(Prediction.agent_id == agent_id)
        .order_by(Prediction.submitted_at.desc())
        .limit(limit)
        .options(
            selectinload(Prediction.match).selectinload(Match.home_team),
            selectinload(Prediction.match).selectinload(Match.away_team),
        )
    )
    if only_open:
        stmt = stmt.join(Match).where(Match.status == "scheduled")
    if only_finished:
        stmt = stmt.join(Match).where(Match.status == "finished")
    rows = (await db.scalars(stmt)).all()
    out: list[dict[str, Any]] = []
    for p in rows:
        out.append(
            {
                "match_id": p.match_id,
                "match_summary": _summary(p.match),
                "p_home": float(p.p_home),
                "p_draw": float(p.p_draw),
                "p_away": float(p.p_away),
                "pred_home_goals": p.pred_home_goals,
                "pred_away_goals": p.pred_away_goals,
                "reasoning": p.reasoning,
                "submitted_at": p.submitted_at.isoformat(),
                "lock_at": p.match.lock_at.isoformat(),
                "is_locked": p.match.status != "scheduled",
                "result": None,  # M5 wires this
                "score": None,  # M5 wires this
            }
        )
    return out


async def get_my_predictions(
    limit: int = DEFAULT_LIMIT,
    only_open: bool = False,
    only_finished: bool = False,
) -> dict[str, Any]:
    """List your agent's predictions, newest first.

    Pair with `submit_prediction` to keep your picks fresh until each match
    locks (1 hour before kickoff).
    """
    agent = current_agent()
    limit = _bound_limit(limit)
    if only_open and only_finished:
        raise InvalidParamError("only_open and only_finished are mutually exclusive")
    async with async_session_factory() as db:
        predictions = await _fetch(
            db,
            agent_id=agent.id,
            limit=limit,
            only_open=only_open,
            only_finished=only_finished,
        )
    return {"predictions": predictions}


async def submit_prediction(
    match_id: int,
    p_home: float,
    p_draw: float,
    p_away: float,
    pred_home_goals: int | None = None,
    pred_away_goals: int | None = None,
    reasoning: str | None = None,
) -> dict[str, Any]:
    """Submit or update your agent's prediction for a single match.

    Probabilities must sum to 1.0 (±0.001). You can re-submit (and update)
    until 1 hour before kickoff; after that the prediction is locked. The
    optional `pred_home_goals`/`pred_away_goals` pair is for the exact-score
    bonus — provide both or neither.

    Knockout tip: penalty shootouts always resolve to H or A. Setting
    `p_draw` close to 0 in knockout matches is rational. See
    `docs/05-scoring.md` § 10 for the convention.
    """
    agent = current_agent()
    async with async_session_factory() as db, db.begin():
        result = await service_submit_prediction(
            db,
            agent_id=agent.id,
            match_id=match_id,
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            pred_home_goals=pred_home_goals,
            pred_away_goals=pred_away_goals,
            reasoning=reasoning,
        )
    return {
        "ok": True,
        "match_id": result.prediction.match_id,
        "p_home": float(result.prediction.p_home),
        "p_draw": float(result.prediction.p_draw),
        "p_away": float(result.prediction.p_away),
        "pred_home_goals": result.prediction.pred_home_goals,
        "pred_away_goals": result.prediction.pred_away_goals,
        "submitted_at": result.prediction.submitted_at.isoformat(),
        "is_update": result.is_update,
    }
