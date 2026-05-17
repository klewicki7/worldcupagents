"""End-to-end tests for resolve_match + override_match."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select, text

from app.db.models.agent import Agent
from app.db.models.human import Human
from app.db.models.prediction import Prediction
from app.db.models.score import Score
from app.db.session import async_session_factory
from app.domain import resolution_service
from app.domain.prediction_service import submit_prediction
from app.lib.errors import (
    AdminInvalidScoreError,
    MatchAlreadyResolvedError,
    MatchCancelledAdminError,
    MatchNotResolvedError,
    MatchTeamsTbdAdminError,
    NotFoundError,
)
from app.lib.tokens import generate_token

pytestmark = pytest.mark.usefixtures("clean_humans")

GROUP_MATCH_ID = 1  # MEX vs RSA, group stage
KNOCKOUT_MATCH_ID = 104  # final, placeholders → MATCH_TEAMS_TBD


async def _seed_human() -> Human:
    async with async_session_factory() as session, session.begin():
        human = Human(google_sub="admin-sub", email="admin@example.com", is_admin=True)
        session.add(human)
        await session.flush()
        await session.refresh(human)
    return human


async def _seed_agent_with_prediction(
    suffix: str,
    *,
    match_id: int = GROUP_MATCH_ID,
    p_home: float = 0.65,
    p_draw: float = 0.20,
    p_away: float = 0.15,
    pred_home_goals: int | None = None,
    pred_away_goals: int | None = None,
) -> Agent:
    _plain, token_hash, token_prefix = generate_token()
    async with async_session_factory() as session, session.begin():
        human = Human(google_sub=f"sub-{suffix}", email=f"u-{suffix}@example.com")
        session.add(human)
        await session.flush()
        agent = Agent(
            human_id=human.id,
            slug=f"agent-{suffix}",
            name=f"agent-{suffix}",
            token_hash=token_hash,
            token_prefix=token_prefix,
        )
        session.add(agent)
        await session.flush()
        await submit_prediction(
            session,
            agent_id=agent.id,
            match_id=match_id,
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            pred_home_goals=pred_home_goals,
            pred_away_goals=pred_away_goals,
            reasoning=None,
        )
        await session.refresh(agent)
    return agent


async def test_resolve_scores_every_prediction() -> None:
    """5 agents predict the same match; resolution writes 5 score rows."""
    admin = await _seed_human()
    agents = []
    for i, probs in enumerate(
        [(0.7, 0.2, 0.1), (0.4, 0.3, 0.3), (0.1, 0.2, 0.7), (0.5, 0.4, 0.1), (0.33, 0.34, 0.33)]
    ):
        a = await _seed_agent_with_prediction(
            str(i), p_home=probs[0], p_draw=probs[1], p_away=probs[2]
        )
        agents.append(a)

    async with async_session_factory() as db, db.begin():
        result = await resolution_service.resolve_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=2,
            away_goals=1,
            actor_human_id=admin.id,
        )

    assert result.outcome == "H"
    assert result.predictions_scored == 5

    async with async_session_factory() as db:
        rows = (await db.scalars(select(Score).where(Score.match_id == GROUP_MATCH_ID))).all()
    assert len(rows) == 5
    by_agent = {r.agent_id: r for r in rows}
    # First agent: p_home=0.7 → brier = (0.7-1)^2 + 0.04 + 0.01 = 0.14
    assert float(by_agent[agents[0].id].brier) == pytest.approx(0.14, abs=1e-6)
    assert all(r.outcome == "H" for r in rows)


async def test_resolve_idempotent_double_call_409() -> None:
    admin = await _seed_human()
    await _seed_agent_with_prediction("solo")

    async with async_session_factory() as db, db.begin():
        await resolution_service.resolve_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=2,
            away_goals=1,
            actor_human_id=admin.id,
        )

    async with async_session_factory() as db, db.begin():
        with pytest.raises(MatchAlreadyResolvedError):
            await resolution_service.resolve_match(
                db,
                match_id=GROUP_MATCH_ID,
                home_goals=2,
                away_goals=1,
                actor_human_id=admin.id,
            )


async def test_resolve_unknown_match() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        with pytest.raises(NotFoundError):
            await resolution_service.resolve_match(
                db,
                match_id=99999,
                home_goals=0,
                away_goals=0,
                actor_human_id=admin.id,
            )


async def test_resolve_cancelled_match() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET status='cancelled' WHERE id=:id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        async with async_session_factory() as db, db.begin():
            with pytest.raises(MatchCancelledAdminError):
                await resolution_service.resolve_match(
                    db,
                    match_id=GROUP_MATCH_ID,
                    home_goals=1,
                    away_goals=0,
                    actor_human_id=admin.id,
                )
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET status='scheduled' WHERE id=:id"),
                {"id": GROUP_MATCH_ID},
            )


async def test_resolve_knockout_with_placeholders_rejected() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        with pytest.raises(MatchTeamsTbdAdminError):
            await resolution_service.resolve_match(
                db,
                match_id=KNOCKOUT_MATCH_ID,
                home_goals=1,
                away_goals=0,
                actor_human_id=admin.id,
            )


async def test_resolve_rejects_negative_goals() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        with pytest.raises(AdminInvalidScoreError):
            await resolution_service.resolve_match(
                db,
                match_id=GROUP_MATCH_ID,
                home_goals=-1,
                away_goals=0,
                actor_human_id=admin.id,
            )


async def test_resolve_group_match_cannot_go_to_penalties() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        with pytest.raises(AdminInvalidScoreError):
            await resolution_service.resolve_match(
                db,
                match_id=GROUP_MATCH_ID,
                home_goals=1,
                away_goals=1,
                went_to_penalties=True,
                penalties_home=4,
                penalties_away=3,
                actor_human_id=admin.id,
            )


async def test_resolve_penalties_require_regulation_tie() -> None:
    admin = await _seed_human()
    # Promote the match to a knockout stage so the went_to_penalties branch is allowed.
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET stage='r32' WHERE id=:id"), {"id": GROUP_MATCH_ID}
        )
    try:
        async with async_session_factory() as db, db.begin():
            with pytest.raises(AdminInvalidScoreError):
                await resolution_service.resolve_match(
                    db,
                    match_id=GROUP_MATCH_ID,
                    home_goals=2,  # not tied
                    away_goals=1,
                    went_to_penalties=True,
                    penalties_home=4,
                    penalties_away=3,
                    actor_human_id=admin.id,
                )
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET stage='group' WHERE id=:id"), {"id": GROUP_MATCH_ID}
            )


async def test_resolve_knockout_with_penalty_shootout() -> None:
    """A knockout decided on PKs: regulation 1-1, PK 4-3 → outcome H; exact-score
    bonus uses regulation goals, so 1-1 prediction with PKs hands +5."""
    admin = await _seed_human()
    # Re-stage match 1 as r32 with the same teams so we can test the penalty path.
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET stage='r32' WHERE id=:id"), {"id": GROUP_MATCH_ID}
        )
    try:
        await _seed_agent_with_prediction(
            "knockout",
            p_home=0.5,
            p_draw=0.0,
            p_away=0.5,
            pred_home_goals=1,
            pred_away_goals=1,
        )
        async with async_session_factory() as db, db.begin():
            result = await resolution_service.resolve_match(
                db,
                match_id=GROUP_MATCH_ID,
                home_goals=1,
                away_goals=1,
                went_to_penalties=True,
                penalties_home=4,
                penalties_away=3,
                actor_human_id=admin.id,
            )
        assert result.outcome == "H"
        assert result.predictions_scored == 1
        async with async_session_factory() as db:
            score = (await db.scalars(select(Score))).one()
        assert score.exact_score_pts == 5  # 1-1 exact match on regulation goals
        assert score.outcome == "H"
        # Brier: p_home=0.5, p_draw=0, p_away=0.5, outcome=H → (0.5-1)^2 + 0 + 0.25 = 0.5
        assert float(score.brier) == pytest.approx(0.5)
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET stage='group' WHERE id=:id"), {"id": GROUP_MATCH_ID}
            )


async def test_cancelled_match_produces_no_scores() -> None:
    admin = await _seed_human()
    await _seed_agent_with_prediction("c")
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET status='cancelled' WHERE id=:id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        async with async_session_factory() as db, db.begin():
            with pytest.raises(MatchCancelledAdminError):
                await resolution_service.resolve_match(
                    db,
                    match_id=GROUP_MATCH_ID,
                    home_goals=1,
                    away_goals=0,
                    actor_human_id=admin.id,
                )
        async with async_session_factory() as db:
            n = await db.scalar(select(Score).where(Score.match_id == GROUP_MATCH_ID))
        assert n is None
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET status='scheduled' WHERE id=:id"),
                {"id": GROUP_MATCH_ID},
            )


async def test_override_rescores_correctly() -> None:
    admin = await _seed_human()
    # 2 agents — one calibrated for ARG win, another for ARG loss.
    a1 = await _seed_agent_with_prediction("o1", p_home=0.7, p_draw=0.2, p_away=0.1)
    a2 = await _seed_agent_with_prediction("o2", p_home=0.1, p_draw=0.2, p_away=0.7)

    # First resolve as home win.
    async with async_session_factory() as db, db.begin():
        await resolution_service.resolve_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=2,
            away_goals=1,
            actor_human_id=admin.id,
        )
    async with async_session_factory() as db:
        before = {
            r.agent_id: float(r.brier)
            for r in (
                await db.scalars(select(Score).where(Score.match_id == GROUP_MATCH_ID))
            ).all()
        }
    assert before[a1.id] < before[a2.id]  # a1 was better-calibrated for H

    # Now override: actually away won 1-2. Roles should flip.
    async with async_session_factory() as db, db.begin():
        result = await resolution_service.override_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=1,
            away_goals=2,
            actor_human_id=admin.id,
            reason="recount",
        )
    assert result.old_outcome == "H"
    assert result.new_outcome == "A"
    assert result.predictions_rescored == 2

    async with async_session_factory() as db:
        rows_after = (
            await db.scalars(select(Score).where(Score.match_id == GROUP_MATCH_ID))
        ).all()
    after = {r.agent_id: float(r.brier) for r in rows_after}
    assert after[a2.id] < after[a1.id]  # a2 now wins
    assert all(r.outcome == "A" for r in rows_after)


async def test_override_requires_already_resolved() -> None:
    admin = await _seed_human()
    async with async_session_factory() as db, db.begin():
        with pytest.raises(MatchNotResolvedError):
            await resolution_service.override_match(
                db,
                match_id=GROUP_MATCH_ID,
                home_goals=1,
                away_goals=0,
                actor_human_id=admin.id,
            )


async def test_audit_log_captures_resolve_and_override() -> None:
    admin = await _seed_human()
    await _seed_agent_with_prediction("audit")
    async with async_session_factory() as db, db.begin():
        await resolution_service.resolve_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=2,
            away_goals=1,
            actor_human_id=admin.id,
        )
    async with async_session_factory() as db, db.begin():
        await resolution_service.override_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=1,
            away_goals=2,
            actor_human_id=admin.id,
            reason="typo",
        )
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT action FROM audit_log WHERE target_id=:t ORDER BY id"
                ),
                {"t": str(GROUP_MATCH_ID)},
            )
        ).all()
    actions = [r[0] for r in rows]
    assert "resolve_match" in actions
    assert "override_match" in actions


async def test_leaderboard_view_reflects_scores() -> None:
    """After resolution, v_agent_leaderboard surfaces avg_brier per agent."""
    admin = await _seed_human()
    a = await _seed_agent_with_prediction("lb", p_home=0.65, p_draw=0.20, p_away=0.15)

    async with async_session_factory() as db, db.begin():
        await resolution_service.resolve_match(
            db,
            match_id=GROUP_MATCH_ID,
            home_goals=2,
            away_goals=1,
            actor_human_id=admin.id,
        )
    async with async_session_factory() as db:
        row = (
            await db.execute(
                text(
                    "SELECT matches_predicted, avg_brier FROM v_agent_leaderboard"
                    " WHERE agent_id = :id"
                ),
                {"id": a.id},
            )
        ).first()
    assert row is not None
    assert row[0] == 1
    assert float(row[1]) == pytest.approx(0.185, abs=1e-6)


# Silence unused warning when running the module in isolation.
_ = UUID, Decimal, Prediction
