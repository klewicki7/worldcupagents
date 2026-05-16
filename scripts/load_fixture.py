"""Loads teams and matches from data/*.yaml into the database.

Usage:
    uv run python -m scripts.load_fixture --all
    uv run python -m scripts.load_fixture --teams-only
    uv run python -m scripts.load_fixture --matches-only
    uv run python -m scripts.load_fixture --dry-run

Idempotent: re-running with unchanged YAML produces zero row changes thanks to
the IS DISTINCT FROM guard on the ON CONFLICT DO UPDATE.

The script runs from anywhere in the repo. It adds backend/ to sys.path so the
`app.*` imports resolve against the existing async engine + session factory.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.db.models import Match, Team  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402

DATA_DIR = ROOT / "data"

TEAM_COLUMNS = (
    "fifa_code",
    "name_en",
    "name_es",
    "flag_emoji",
    "group_letter",
    "confederation",
)
MATCH_COLUMNS = (
    "stage",
    "group_letter",
    "home_team_id",
    "away_team_id",
    "home_placeholder",
    "away_placeholder",
    "kickoff_at",
    "venue_city",
    "venue_country",
)

GROUP_STAGES = {"group"}
KNOCKOUT_STAGES = {"r32", "r16", "qf", "sf", "third", "final"}


def _load_yaml(path: Path, top_key: str) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text())
    if isinstance(raw, list):
        return raw
    return raw[top_key]


def _validate_teams(teams: list[dict[str, Any]]) -> None:
    if len(teams) != 48:
        raise ValueError(f"teams.yaml must contain 48 entries, got {len(teams)}")
    ids = sorted(t["id"] for t in teams)
    if ids != list(range(1, 49)):
        raise ValueError(f"team IDs must be contiguous 1..48, got {ids}")


def _validate_matches(matches: list[dict[str, Any]]) -> None:
    if len(matches) != 104:
        raise ValueError(f"matches.yaml must contain 104 entries, got {len(matches)}")
    ids = sorted(m["id"] for m in matches)
    if ids != list(range(1, 105)):
        raise ValueError(f"match IDs must be contiguous 1..104, got {ids}")
    for m in matches:
        if m["kickoff_at"] is None:
            raise ValueError(f"match {m['id']} missing kickoff_at")
        stage = m["stage"]
        if stage in GROUP_STAGES:
            if m.get("home_team_id") is None or m.get("away_team_id") is None:
                raise ValueError(f"group-stage match {m['id']} missing team IDs")
            if m.get("home_placeholder") or m.get("away_placeholder"):
                raise ValueError(f"group-stage match {m['id']} must not have placeholders")
        elif stage in KNOCKOUT_STAGES:
            if m.get("home_team_id") is not None or m.get("away_team_id") is not None:
                raise ValueError(
                    f"knockout match {m['id']} must not have team IDs at fixture-load time"
                )
            if not m.get("home_placeholder") or not m.get("away_placeholder"):
                raise ValueError(f"knockout match {m['id']} missing placeholder strings")
        else:
            raise ValueError(f"match {m['id']} has unknown stage {stage!r}")


async def load_teams(*, dry_run: bool = False) -> dict[str, int]:
    teams = _load_yaml(DATA_DIR / "teams.yaml", "teams")
    _validate_teams(teams)
    if dry_run:
        print(f"[dry-run] would upsert teams: {len(teams)}")
        return {"total_in_yaml": len(teams), "changed": 0}

    async with async_session_factory() as session:
        stmt = insert(Team).values(teams)
        excluded = stmt.excluded
        update_cols = {col: excluded[col] for col in TEAM_COLUMNS}
        # IS DISTINCT FROM guard across all updatable columns to make the upsert a true no-op
        # when YAML matches the DB. Without it, ON CONFLICT DO UPDATE rewrites identical rows.
        distinct_filter = None
        for col in TEAM_COLUMNS:
            term = Team.__table__.c[col].is_distinct_from(excluded[col])
            distinct_filter = term if distinct_filter is None else distinct_filter | term
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_cols,
            where=distinct_filter,
        )
        result = await session.execute(stmt)
        await session.commit()
        changed = result.rowcount or 0
        print(f"Loaded teams: {len(teams)} ({changed} changed)")
        return {"total_in_yaml": len(teams), "changed": changed}


async def load_matches(*, dry_run: bool = False) -> dict[str, int]:
    matches = _load_yaml(DATA_DIR / "matches.yaml", "matches")
    _validate_matches(matches)
    if dry_run:
        print(f"[dry-run] would upsert matches: {len(matches)}")
        return {"total_in_yaml": len(matches), "changed": 0}

    # lock_at is NOT NULL but the trigger fills it on INSERT/UPDATE OF kickoff_at.
    # We must supply *something* for INSERT to satisfy the column constraint before the trigger
    # fires; the trigger then overwrites it. Easiest: copy kickoff_at as a placeholder.
    rows = []
    for m in matches:
        kickoff_dt = datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00"))
        row = {col: m.get(col) for col in MATCH_COLUMNS}
        row["id"] = m["id"]
        row["kickoff_at"] = kickoff_dt
        row["lock_at"] = kickoff_dt  # trigger will overwrite to kickoff_at - 1h
        rows.append(row)

    async with async_session_factory() as session:
        stmt = insert(Match).values(rows)
        excluded = stmt.excluded
        update_cols = {col: excluded[col] for col in MATCH_COLUMNS}
        distinct_filter = None
        for col in MATCH_COLUMNS:
            term = Match.__table__.c[col].is_distinct_from(excluded[col])
            distinct_filter = term if distinct_filter is None else distinct_filter | term
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_=update_cols,
            where=distinct_filter,
        )
        result = await session.execute(stmt)
        await session.commit()
        changed = result.rowcount or 0
        print(f"Loaded matches: {len(matches)} ({changed} changed)")
        return {"total_in_yaml": len(matches), "changed": changed}


async def _run(args: argparse.Namespace) -> None:
    try:
        if args.teams_only or args.all:
            await load_teams(dry_run=args.dry_run)
        if args.matches_only or args.all:
            await load_matches(dry_run=args.dry_run)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load worldcupagents fixture data into Postgres.")
    parser.add_argument("--all", action="store_true", help="load teams and matches (default)")
    parser.add_argument("--teams-only", action="store_true")
    parser.add_argument("--matches-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="validate YAML, no DB writes")
    args = parser.parse_args()
    if not (args.teams_only or args.matches_only):
        args.all = True
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
