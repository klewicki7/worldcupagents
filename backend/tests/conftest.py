"""Phase 0 test harness.

Session-scoped fixture that brings the local Postgres to a known seeded state:
runs `alembic upgrade head` via subprocess (avoids the nested-asyncio.run loop
collision that arises if we drive Alembic from inside a pytest-asyncio fixture)
and then loads teams + matches via the same loader the Makefile uses.

# TODO: Phase 0 tests share the local dev DB — no testcontainers, no rollback.
# Introduce transactional fixtures (or per-test schemas) when write-mutating
# tests are added in later milestones. See design.md § 7.1 / ADR-9.
"""
from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# Make scripts/load_fixture.py importable (sibling of backend/).
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.load_fixture import load_matches, load_teams  # noqa: E402

from app.api.rate_limit import limiter  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepared_db():
    backend_dir = ROOT / "backend"
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        check=True,
    )
    await load_teams()
    await load_matches()
    yield


@pytest_asyncio.fixture
async def clean_humans() -> AsyncIterator[None]:
    """Wipe humans + agents + audit_log between tests + reset the in-memory rate limiter.

    Predictions/scores cascade through agents.human_id ON DELETE CASCADE.
    Teams and matches stay (loaded once by the session fixture).
    """
    async with async_session_factory() as session, session.begin():
        await session.execute(text("TRUNCATE humans, agents, audit_log RESTART IDENTITY CASCADE"))
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient bound to the FastAPI app via ASGITransport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
