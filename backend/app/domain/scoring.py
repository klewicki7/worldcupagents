"""Pure scoring functions. No DB, no I/O. See `docs/05-scoring.md`.

The three functions here are the only place Brier and exact-score math live.
Everything downstream (resolution service, leaderboard view) reads the values
they produce. Keeping the math here makes auditing trivial.
"""

from __future__ import annotations

from typing import Literal

Outcome = Literal["H", "D", "A"]


def multiclass_brier(
    p_home: float, p_draw: float, p_away: float, outcome: Outcome
) -> float:
    """Multiclass Brier score for a single match prediction.

    `outcome` is one-hot-encoded as (1,0,0)/(0,1,0)/(0,0,1) for H/D/A; the
    Brier score is the sum of squared deviations between predicted probability
    and the one-hot outcome. Range [0, 2]; lower is better; 0 is perfect.

    No clamping or normalization: callers must validate `0 <= p_* <= 1` and
    `sum ≈ 1` upstream (the `submit_prediction` path already does).
    """
    o_home = 1.0 if outcome == "H" else 0.0
    o_draw = 1.0 if outcome == "D" else 0.0
    o_away = 1.0 if outcome == "A" else 0.0
    return (
        (p_home - o_home) ** 2
        + (p_draw - o_draw) ** 2
        + (p_away - o_away) ** 2
    )


def exact_score_points(
    pred_home: int | None,
    pred_away: int | None,
    actual_home: int,
    actual_away: int,
) -> int:
    """0 if no exact-score prediction, 5 if exact, 2 if goal difference matches, else 0.

    Uses regulation/extra-time goals only — penalty shootout score is irrelevant
    for the exact-score bonus (per spec § 10).
    """
    if pred_home is None or pred_away is None:
        return 0
    if pred_home == actual_home and pred_away == actual_away:
        return 5
    if (pred_home - pred_away) == (actual_home - actual_away):
        return 2
    return 0


def determine_outcome(
    home_goals: int,
    away_goals: int,
    *,
    went_to_penalties: bool = False,
    penalties_home: int | None = None,
    penalties_away: int | None = None,
) -> Outcome:
    """Map a finished-match record to its outcome label.

    Knockouts decided by penalties produce H or A based on the shootout —
    never D — which matches FIFA's official ruling. Regulation/ET tie is only
    `D` in group stage where draws stand.
    """
    if went_to_penalties:
        if penalties_home is None or penalties_away is None:
            raise ValueError("penalty scores required when went_to_penalties=True")
        if penalties_home == penalties_away:
            raise ValueError("penalty shootout cannot end tied")
        return "H" if penalties_home > penalties_away else "A"
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"
