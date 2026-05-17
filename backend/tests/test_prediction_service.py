"""Unit + service-level tests for submit_prediction business logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.db.models.prediction import Prediction
from app.db.session import async_session_factory
from app.domain.prediction_service import submit_prediction
from app.mcp.errors import (
    InvalidProbabilitiesError,
    InvalidScoreError,
    MatchCancelledError,
    MatchNotFoundError,
    MatchTeamsTbdError,
    PredictionLockedError,
    ReasoningTooLongError,
)

pytestmark = pytest.mark.usefixtures("clean_humans")

# data/matches.yaml: id=1 is MEX vs RSA (group A), in the future.
# id=104 is the final (knockout placeholders → team_id NULL).
GROUP_MATCH_ID = 1
KNOCKOUT_MATCH_ID = 104


async def _kwargs(agent_id, match_id=GROUP_MATCH_ID, **over):  # type: ignore[no-untyped-def]
    base = dict(
        agent_id=agent_id,
        match_id=match_id,
        p_home=0.65,
        p_draw=0.20,
        p_away=0.15,
        pred_home_goals=None,
        pred_away_goals=None,
        reasoning=None,
    )
    base.update(over)
    return base


async def test_submit_happy_path(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        result = await submit_prediction(db, **(await _kwargs(agent.id)))
    assert result.is_update is False
    assert result.prediction.match_id == GROUP_MATCH_ID
    assert float(result.prediction.p_home) == 0.65


async def test_submit_with_exact_score(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        result = await submit_prediction(
            db, **(await _kwargs(agent.id, pred_home_goals=2, pred_away_goals=0))
        )
    assert result.prediction.pred_home_goals == 2
    assert result.prediction.pred_away_goals == 0


async def test_resubmit_is_update_and_snapshots_history(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await submit_prediction(db, **(await _kwargs(agent.id)))
    async with async_session_factory() as db, db.begin():
        result2 = await submit_prediction(
            db, **(await _kwargs(agent.id, p_home=0.5, p_draw=0.3, p_away=0.2))
        )
    assert result2.is_update is True

    # Trigger writes a history row on each INSERT + each UPDATE → 2 rows total.
    async with async_session_factory() as db:
        count = await db.scalar(text("SELECT COUNT(*) FROM prediction_history"))
        latest = (
            await db.execute(
                text(
                    "SELECT p_home FROM prediction_history"
                    " ORDER BY snapshotted_at DESC LIMIT 1"
                )
            )
        ).scalar()
    assert count == 2
    assert float(latest) == 0.5


async def test_match_not_found(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(MatchNotFoundError):
            await submit_prediction(db, **(await _kwargs(agent.id, match_id=99999)))


async def test_match_cancelled(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET status = 'cancelled' WHERE id = :id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        async with async_session_factory() as db, db.begin():
            with pytest.raises(MatchCancelledError):
                await submit_prediction(db, **(await _kwargs(agent.id)))
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET status = 'scheduled' WHERE id = :id"),
                {"id": GROUP_MATCH_ID},
            )


async def test_match_teams_tbd_on_knockout_placeholder(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(MatchTeamsTbdError):
            await submit_prediction(db, **(await _kwargs(agent.id, match_id=KNOCKOUT_MATCH_ID)))


async def test_prediction_locked(seeded_agent) -> None:
    """Move a match's lock_at to the past and assert PREDICTION_LOCKED.

    Note: updating `lock_at` directly skips the `set_lock_at` BEFORE-trigger
    because that trigger only fires on `kickoff_at` changes.
    """
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET lock_at = now() - interval '1 hour' WHERE id = :id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        async with async_session_factory() as db, db.begin():
            with pytest.raises(PredictionLockedError):
                await submit_prediction(db, **(await _kwargs(agent.id)))
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text(
                    "UPDATE matches SET lock_at = kickoff_at - interval '1 hour'"
                    " WHERE id = :id"
                ),
                {"id": GROUP_MATCH_ID},
            )


async def test_prediction_locked_uses_injected_now(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(PredictionLockedError):
            await submit_prediction(
                db,
                **(await _kwargs(agent.id)),
                now=datetime.now(UTC) + timedelta(days=365),
            )


@pytest.mark.parametrize(
    ("p_home", "p_draw", "p_away"),
    [
        (0.6, 0.3, 0.2),  # sum 1.1 > tolerance
        (0.5, 0.3, 0.1),  # sum 0.9 < tolerance
        (-0.1, 0.5, 0.6),  # out of range
        (1.2, 0.0, -0.2),  # out of range
    ],
)
async def test_invalid_probabilities(seeded_agent, p_home, p_draw, p_away) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(InvalidProbabilitiesError):
            await submit_prediction(
                db, **(await _kwargs(agent.id, p_home=p_home, p_draw=p_draw, p_away=p_away))
            )


async def test_invalid_score_one_set(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(InvalidScoreError):
            await submit_prediction(
                db, **(await _kwargs(agent.id, pred_home_goals=2, pred_away_goals=None))
            )


async def test_invalid_score_out_of_range(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(InvalidScoreError):
            await submit_prediction(
                db, **(await _kwargs(agent.id, pred_home_goals=20, pred_away_goals=0))
            )


async def test_reasoning_too_long(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        with pytest.raises(ReasoningTooLongError):
            await submit_prediction(
                db, **(await _kwargs(agent.id, reasoning="x" * 501))
            )


async def test_prediction_persisted_in_db(seeded_agent) -> None:
    agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await submit_prediction(db, **(await _kwargs(agent.id)))
    async with async_session_factory() as db:
        row = await db.scalar(
            select(Prediction).where(
                Prediction.agent_id == agent.id, Prediction.match_id == GROUP_MATCH_ID
            )
        )
    assert row is not None
    assert float(row.p_home) == 0.65
