"""Exhaustive unit tests for the pure scoring functions."""

from __future__ import annotations

import math

import pytest

from app.domain.scoring import determine_outcome, exact_score_points, multiclass_brier


class TestMulticlassBrier:
    def test_perfect_home_is_zero(self) -> None:
        assert multiclass_brier(1.0, 0.0, 0.0, "H") == 0.0

    def test_perfect_draw_is_zero(self) -> None:
        assert multiclass_brier(0.0, 1.0, 0.0, "D") == 0.0

    def test_perfect_away_is_zero(self) -> None:
        assert multiclass_brier(0.0, 0.0, 1.0, "A") == 0.0

    def test_worst_case_is_two(self) -> None:
        # All mass on something that didn't happen.
        assert multiclass_brier(1.0, 0.0, 0.0, "A") == pytest.approx(2.0)

    def test_uniform_baseline(self) -> None:
        # Maximum-entropy guess (1/3, 1/3, 1/3) — should be ~0.6667 regardless of outcome.
        third = 1.0 / 3.0
        for outcome in ("H", "D", "A"):
            assert multiclass_brier(third, third, third, outcome) == pytest.approx(2.0 / 3.0)

    def test_spec_example_argentina_wins(self) -> None:
        # From docs/05-scoring.md § 2.
        score = multiclass_brier(0.65, 0.20, 0.15, "H")
        assert score == pytest.approx(0.185)

    def test_spec_example_argentina_draws(self) -> None:
        score = multiclass_brier(0.65, 0.20, 0.15, "D")
        assert score == pytest.approx(1.085)

    def test_symmetric_in_swapped_classes(self) -> None:
        # Swapping H <-> A flips outcome and prob assignment; Brier should be the same.
        a = multiclass_brier(0.65, 0.20, 0.15, "H")
        b = multiclass_brier(0.15, 0.20, 0.65, "A")
        assert a == pytest.approx(b)


class TestExactScorePoints:
    def test_no_prediction_returns_zero(self) -> None:
        assert exact_score_points(None, None, 2, 1) == 0
        assert exact_score_points(None, 1, 2, 1) == 0
        assert exact_score_points(2, None, 2, 1) == 0

    def test_exact_match_returns_five(self) -> None:
        assert exact_score_points(2, 1, 2, 1) == 5

    def test_exact_zero_zero(self) -> None:
        assert exact_score_points(0, 0, 0, 0) == 5

    def test_goal_difference_only_returns_two(self) -> None:
        # Pred 3-1 (diff +2), actual 2-0 (diff +2).
        assert exact_score_points(3, 1, 2, 0) == 2

    def test_goal_difference_negative(self) -> None:
        assert exact_score_points(1, 3, 0, 2) == 2

    def test_wrong_direction_returns_zero(self) -> None:
        # Pred 2-1 (home wins), actual 1-2 (away wins).
        assert exact_score_points(2, 1, 1, 2) == 0

    def test_close_but_no_match_returns_zero(self) -> None:
        assert exact_score_points(2, 1, 3, 1) == 0  # diff +1 vs +2

    def test_penalty_shootout_does_not_change_exact_score(self) -> None:
        # Per docs/05-scoring.md § 4: exact-score uses regulation/ET goals,
        # ignoring the shootout. So predicting 1-1 against an actual 1-1 (PK 4-3)
        # still scores +5 — the function takes regulation goals as its inputs.
        assert exact_score_points(1, 1, 1, 1) == 5


class TestDetermineOutcome:
    def test_home_wins(self) -> None:
        assert determine_outcome(2, 1) == "H"

    def test_away_wins(self) -> None:
        assert determine_outcome(0, 1) == "A"

    def test_draw(self) -> None:
        assert determine_outcome(1, 1) == "D"

    def test_penalties_home_wins(self) -> None:
        assert (
            determine_outcome(
                1, 1, went_to_penalties=True, penalties_home=4, penalties_away=3
            )
            == "H"
        )

    def test_penalties_away_wins(self) -> None:
        assert (
            determine_outcome(
                2, 2, went_to_penalties=True, penalties_home=2, penalties_away=4
            )
            == "A"
        )

    def test_penalties_missing_data_raises(self) -> None:
        with pytest.raises(ValueError):
            determine_outcome(1, 1, went_to_penalties=True)
        with pytest.raises(ValueError):
            determine_outcome(1, 1, went_to_penalties=True, penalties_home=3)

    def test_penalties_tie_raises(self) -> None:
        with pytest.raises(ValueError):
            determine_outcome(
                1, 1, went_to_penalties=True, penalties_home=3, penalties_away=3
            )


class TestBrierRange:
    @pytest.mark.parametrize(
        ("p_home", "p_draw", "p_away"),
        [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.5, 0.5, 0.0),
            (0.34, 0.33, 0.33),
            (0.1, 0.1, 0.8),
        ],
    )
    def test_score_in_bounds(self, p_home: float, p_draw: float, p_away: float) -> None:
        for outcome in ("H", "D", "A"):
            score = multiclass_brier(p_home, p_draw, p_away, outcome)
            assert 0.0 <= score <= 2.0
            assert math.isfinite(score)
