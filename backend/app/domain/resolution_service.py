"""Admin-only match resolution.

`resolve_match` is called when a match goes from `scheduled`/`live` → `finished`.
`override_match` corrects a wrong result on an already-finished match — it deletes
existing `scores` rows for the match and re-runs scoring with the new result.

Both wrap the writes in a SERIALIZABLE transaction (per `docs/09-roadmap.md` M5)
plus `SELECT ... FOR UPDATE` on the match row to serialize concurrent admin
resolves. Scoring goes through `INSERT ... ON CONFLICT DO UPDATE` so the operation
is naturally idempotent at the row level even under retries.

Predictions submitted *after* `lock_at` are excluded defensively (per scoring spec
§ 10); the prediction write path already rejects them, but if one slips in we
don't reward it. Backfill = re-running `resolve_match` (rejected because already
resolved) or `override_match` (allowed) — both end up scoring every eligible
prediction for the match.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import write_audit
from app.db.models.match import Match
from app.db.models.prediction import Prediction
from app.db.models.score import Score
from app.domain.scoring import Outcome, determine_outcome, exact_score_points, multiclass_brier
from app.lib.errors import (
    AdminInvalidScoreError,
    MatchAlreadyResolvedError,
    MatchCancelledAdminError,
    MatchNotResolvedError,
    MatchTeamsTbdAdminError,
    NotFoundError,
)


@dataclass(frozen=True, slots=True)
class ResolveResult:
    match_id: int
    outcome: Outcome
    predictions_scored: int
    resolved_at: datetime


@dataclass(frozen=True, slots=True)
class OverrideResult:
    match_id: int
    old_outcome: Outcome | None
    new_outcome: Outcome
    predictions_rescored: int
    overridden_at: datetime


def _validate_score(
    *,
    stage: str,
    home_goals: int,
    away_goals: int,
    went_to_penalties: bool,
    penalties_home: int | None,
    penalties_away: int | None,
) -> None:
    if home_goals < 0 or away_goals < 0:
        raise AdminInvalidScoreError("goals must be non-negative")
    if went_to_penalties:
        if stage == "group":
            raise AdminInvalidScoreError("group matches cannot go to penalties")
        if home_goals != away_goals:
            raise AdminInvalidScoreError("penalties only after a regulation tie")
        if penalties_home is None or penalties_away is None:
            raise AdminInvalidScoreError("penalty scores required")
        if penalties_home < 0 or penalties_away < 0:
            raise AdminInvalidScoreError("penalty scores must be non-negative")
        if penalties_home == penalties_away:
            raise AdminInvalidScoreError("penalty shootout cannot end tied")
    else:
        if penalties_home is not None or penalties_away is not None:
            raise AdminInvalidScoreError(
                "penalty scores require went_to_penalties=true"
            )


def _to_decimal(brier: float) -> Decimal:
    # NUMERIC(7,6) holds values up to 9.999999; Brier is in [0, 2] so this fits.
    return Decimal(f"{brier:.6f}")


async def _score_all_predictions(
    db: AsyncSession,
    *,
    match: Match,
    outcome: Outcome,
) -> int:
    """Iterate predictions for the match, upsert one Score row each, return count.

    Excludes any prediction with `submitted_at > match.lock_at` per scoring § 10
    (defensive: prediction service rejects these, but never trust the wire).
    """
    stmt = (
        select(Prediction)
        .where(Prediction.match_id == match.id)
        .where(Prediction.submitted_at <= match.lock_at)
    )
    predictions = (await db.scalars(stmt)).all()
    scored = 0
    for p in predictions:
        brier = multiclass_brier(
            float(p.p_home), float(p.p_draw), float(p.p_away), outcome
        )
        exact_pts = exact_score_points(
            p.pred_home_goals,
            p.pred_away_goals,
            match.home_goals or 0,
            match.away_goals or 0,
        )
        upsert = pg_insert(Score).values(
            agent_id=p.agent_id,
            match_id=match.id,
            brier=_to_decimal(brier),
            exact_score_pts=exact_pts,
            outcome=outcome,
        )
        upsert = upsert.on_conflict_do_update(
            index_elements=["agent_id", "match_id"],
            set_={
                "brier": upsert.excluded.brier,
                "exact_score_pts": upsert.excluded.exact_score_pts,
                "outcome": upsert.excluded.outcome,
            },
        )
        await db.execute(upsert)
        scored += 1
    return scored


async def resolve_match(
    db: AsyncSession,
    *,
    match_id: int,
    home_goals: int,
    away_goals: int,
    went_to_penalties: bool = False,
    penalties_home: int | None = None,
    penalties_away: int | None = None,
    actor_human_id: UUID,
) -> ResolveResult:
    """Mark a `scheduled`/`live` match as `finished` and score all predictions.

    Raises:
        NotFoundError: no such match_id.
        MatchAlreadyResolvedError: status is already `finished` — use override.
        MatchCancelledAdminError: status is `cancelled` — re-open via PATCH first.
        MatchTeamsTbdAdminError: knockout has unfilled team slots.
        AdminInvalidScoreError: score doesn't validate (negative, penalty rules).
    """
    # `FOR UPDATE` on the match row serializes concurrent resolves of the same
    # match; combined with the unique (agent_id, match_id) PK on `scores`, the
    # critical section is safe under READ COMMITTED. SERIALIZABLE buys nothing
    # here and SQLAlchemy 2.x rejects per-statement isolation-level swaps anyway.
    match = await db.scalar(
        select(Match).where(Match.id == match_id).with_for_update()
    )
    if match is None:
        raise NotFoundError(f"no match with id={match_id}")
    if match.status == "finished":
        raise MatchAlreadyResolvedError("match is already resolved")
    if match.status == "cancelled":
        raise MatchCancelledAdminError("match is cancelled")
    if match.home_team_id is None or match.away_team_id is None:
        raise MatchTeamsTbdAdminError("knockout teams not yet assigned")

    _validate_score(
        stage=match.stage,
        home_goals=home_goals,
        away_goals=away_goals,
        went_to_penalties=went_to_penalties,
        penalties_home=penalties_home,
        penalties_away=penalties_away,
    )

    now = datetime.now(UTC)
    match.home_goals = home_goals
    match.away_goals = away_goals
    match.went_to_penalties = went_to_penalties
    match.penalties_home = penalties_home
    match.penalties_away = penalties_away
    match.status = "finished"
    match.resolved_at = now
    await db.flush()

    outcome = determine_outcome(
        home_goals,
        away_goals,
        went_to_penalties=went_to_penalties,
        penalties_home=penalties_home,
        penalties_away=penalties_away,
    )
    scored = await _score_all_predictions(db, match=match, outcome=outcome)

    await write_audit(
        db,
        actor_type="admin",
        actor_id=actor_human_id,
        action="resolve_match",
        target_type="match",
        target_id=str(match_id),
        metadata={
            "home_goals": home_goals,
            "away_goals": away_goals,
            "went_to_penalties": went_to_penalties,
            "penalties_home": penalties_home,
            "penalties_away": penalties_away,
            "outcome": outcome,
            "predictions_scored": scored,
        },
    )

    return ResolveResult(
        match_id=match_id,
        outcome=outcome,
        predictions_scored=scored,
        resolved_at=now,
    )


async def override_match(
    db: AsyncSession,
    *,
    match_id: int,
    home_goals: int,
    away_goals: int,
    went_to_penalties: bool = False,
    penalties_home: int | None = None,
    penalties_away: int | None = None,
    actor_human_id: UUID,
    reason: str | None = None,
) -> OverrideResult:
    """Correct a wrong result. Deletes existing scores then re-runs scoring.

    Requires the match to be already `finished` — call `resolve_match` first
    to set the initial result.
    """
    match = await db.scalar(
        select(Match).where(Match.id == match_id).with_for_update()
    )
    if match is None:
        raise NotFoundError(f"no match with id={match_id}")
    if match.status != "finished":
        raise MatchNotResolvedError("can only override an already-resolved match")
    if match.home_team_id is None or match.away_team_id is None:
        raise MatchTeamsTbdAdminError("knockout teams not yet assigned")

    _validate_score(
        stage=match.stage,
        home_goals=home_goals,
        away_goals=away_goals,
        went_to_penalties=went_to_penalties,
        penalties_home=penalties_home,
        penalties_away=penalties_away,
    )

    old_outcome = determine_outcome(
        match.home_goals or 0,
        match.away_goals or 0,
        went_to_penalties=match.went_to_penalties,
        penalties_home=match.penalties_home,
        penalties_away=match.penalties_away,
    )
    old_payload = {
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "went_to_penalties": match.went_to_penalties,
        "penalties_home": match.penalties_home,
        "penalties_away": match.penalties_away,
        "outcome": old_outcome,
    }

    now = datetime.now(UTC)
    match.home_goals = home_goals
    match.away_goals = away_goals
    match.went_to_penalties = went_to_penalties
    match.penalties_home = penalties_home
    match.penalties_away = penalties_away
    match.resolved_at = now
    await db.flush()

    # Wipe existing scores for this match — re-scoring rebuilds them.
    await db.execute(delete(Score).where(Score.match_id == match_id))

    outcome = determine_outcome(
        home_goals,
        away_goals,
        went_to_penalties=went_to_penalties,
        penalties_home=penalties_home,
        penalties_away=penalties_away,
    )
    scored = await _score_all_predictions(db, match=match, outcome=outcome)

    await write_audit(
        db,
        actor_type="admin",
        actor_id=actor_human_id,
        action="override_match",
        target_type="match",
        target_id=str(match_id),
        metadata={
            "old": old_payload,
            "new": {
                "home_goals": home_goals,
                "away_goals": away_goals,
                "went_to_penalties": went_to_penalties,
                "penalties_home": penalties_home,
                "penalties_away": penalties_away,
                "outcome": outcome,
            },
            "predictions_rescored": scored,
            "reason": reason,
        },
    )

    return OverrideResult(
        match_id=match_id,
        old_outcome=old_outcome,
        new_outcome=outcome,
        predictions_rescored=scored,
        overridden_at=now,
    )
