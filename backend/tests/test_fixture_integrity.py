"""Encodes the 6 verification queries from docs/07-fixture-loading.md § 8
against the seeded local DB, plus an idempotency assertion."""
from __future__ import annotations

from sqlalchemy import text

from app.db.session import async_session_factory
from scripts.load_fixture import load_matches, load_teams


async def test_teams_count() -> None:
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM teams"))
        assert result.scalar_one() == 48, "expected 48 teams"


async def test_teams_per_group() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT group_letter, COUNT(*) FROM teams GROUP BY group_letter")
        )
        per_group = {row[0]: row[1] for row in result.all()}
    assert set(per_group.keys()) == set("ABCDEFGHIJKL"), f"groups: {sorted(per_group)}"
    for letter, count in per_group.items():
        assert count == 4, f"group {letter} has {count} teams, expected 4"


async def test_matches_count() -> None:
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM matches"))
        assert result.scalar_one() == 104, "expected 104 matches"


async def test_stage_distribution() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT stage, COUNT(*) FROM matches GROUP BY stage")
        )
        dist = {row[0]: row[1] for row in result.all()}
    assert dist == {"group": 72, "r32": 16, "r16": 8, "qf": 4, "sf": 2, "third": 1, "final": 1}


async def test_group_matches_have_teams() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM matches WHERE stage='group' "
                "AND (home_team_id IS NULL OR away_team_id IS NULL)"
            )
        )
        assert result.scalar_one() == 0, "every group match must have both team IDs"


async def test_lock_at_invariant() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM matches WHERE lock_at != kickoff_at - INTERVAL '1 hour'")
        )
        assert result.scalar_one() == 0, "lock_at trigger must set kickoff_at - 1h on every match"


async def test_loader_idempotent() -> None:
    # teams table has no updated_at by design (static reference data); use matches as the witness.
    async with async_session_factory() as session:
        before = (await session.execute(text("SELECT max(updated_at) FROM matches"))).scalar_one()
    teams_result = await load_teams()
    matches_result = await load_matches()
    assert teams_result["changed"] == 0, "teams loader must be idempotent"
    assert matches_result["changed"] == 0, "matches loader must be idempotent"
    async with async_session_factory() as session:
        after = (await session.execute(text("SELECT max(updated_at) FROM matches"))).scalar_one()
    assert before == after, "matches updated_at must not bump on a clean re-load"
