"""Business logic for `submit_prediction`.

Validates probabilities + exact-score pair + reasoning, enforces lock_at on
every write path (per `CLAUDE.md`), and upserts to `predictions`. The DB
trigger `snapshot_prediction_history` writes a history row on every INSERT
or UPDATE; we don't snapshot manually.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match import Match
from app.db.models.prediction import Prediction
from app.mcp.errors import (
    InvalidProbabilitiesError,
    InvalidScoreError,
    MatchCancelledError,
    MatchNotFoundError,
    MatchTeamsTbdError,
    PredictionLockedError,
    ReasoningTooLongError,
)

PROB_TOLERANCE = 0.001
SCORE_MIN = 0
SCORE_MAX = 15
REASONING_MAX = 500


@dataclass(frozen=True, slots=True)
class SubmitResult:
    prediction: Prediction
    is_update: bool


def _validate_probabilities(p_home: float, p_draw: float, p_away: float) -> None:
    for label, value in (("p_home", p_home), ("p_draw", p_draw), ("p_away", p_away)):
        if not (0.0 <= value <= 1.0):
            raise InvalidProbabilitiesError(
                f"{label} must be in [0, 1]", {"field": label, "value": value}
            )
    total = p_home + p_draw + p_away
    if abs(total - 1.0) > PROB_TOLERANCE:
        raise InvalidProbabilitiesError(
            "probabilities must sum to 1.0 (±0.001)",
            {"sum": total, "tolerance": PROB_TOLERANCE},
        )


def _validate_exact_score(home: int | None, away: int | None) -> None:
    if (home is None) != (away is None):
        raise InvalidScoreError("both `pred_home_goals` and `pred_away_goals` are required, or neither")
    if home is None:
        return
    assert away is not None
    for label, value in (("pred_home_goals", home), ("pred_away_goals", away)):
        if not (SCORE_MIN <= value <= SCORE_MAX):
            raise InvalidScoreError(
                f"{label} must be in [{SCORE_MIN}, {SCORE_MAX}]",
                {"field": label, "value": value},
            )


def _validate_reasoning(reasoning: str | None) -> str | None:
    if reasoning is None:
        return None
    if len(reasoning) > REASONING_MAX:
        raise ReasoningTooLongError(len(reasoning))
    stripped = reasoning.strip()
    return stripped or None


def _decimal(value: float) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


async def submit_prediction(
    db: AsyncSession,
    *,
    agent_id: UUID,
    match_id: int,
    p_home: float,
    p_draw: float,
    p_away: float,
    pred_home_goals: int | None,
    pred_away_goals: int | None,
    reasoning: str | None,
    now: datetime | None = None,
) -> SubmitResult:
    """Insert or update an agent's prediction for one match.

    Raises one of the MCP error codes from `04-mcp-spec.md` § 4.4 on any
    validation/lock/lookup failure. On success, the surrounding session's commit
    fires the `snapshot_prediction_history` trigger (verified by tests).
    """
    _validate_probabilities(p_home, p_draw, p_away)
    _validate_exact_score(pred_home_goals, pred_away_goals)
    reasoning_clean = _validate_reasoning(reasoning)

    match = await db.get(Match, match_id)
    if match is None:
        raise MatchNotFoundError(match_id)
    if match.status == "cancelled":
        raise MatchCancelledError(match_id)
    if match.home_team_id is None or match.away_team_id is None:
        raise MatchTeamsTbdError(match_id)

    current_time = now or datetime.now(UTC)
    lock_at = match.lock_at
    if lock_at.tzinfo is None:
        # Defensive: should never happen given TIMESTAMPTZ, but if a test fixture
        # bypasses the trigger, normalize so the comparison is well-defined.
        lock_at = lock_at.replace(tzinfo=UTC)
    if current_time >= lock_at:
        raise PredictionLockedError(lock_at.isoformat())

    existing = await db.scalar(
        select(Prediction).where(
            Prediction.agent_id == agent_id, Prediction.match_id == match_id
        )
    )
    is_update = existing is not None

    if existing is None:
        prediction = Prediction(
            agent_id=agent_id,
            match_id=match_id,
            p_home=_decimal(p_home),
            p_draw=_decimal(p_draw),
            p_away=_decimal(p_away),
            pred_home_goals=pred_home_goals,
            pred_away_goals=pred_away_goals,
            reasoning=reasoning_clean,
        )
        db.add(prediction)
    else:
        existing.p_home = _decimal(p_home)
        existing.p_draw = _decimal(p_draw)
        existing.p_away = _decimal(p_away)
        existing.pred_home_goals = pred_home_goals
        existing.pred_away_goals = pred_away_goals
        existing.reasoning = reasoning_clean
        prediction = existing

    await db.flush()
    return SubmitResult(prediction=prediction, is_update=is_update)
