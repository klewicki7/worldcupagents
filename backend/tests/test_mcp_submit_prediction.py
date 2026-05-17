"""MCP tool tests: submit_prediction + per-agent rate limit.

Tool-level tests bind `current_agent` via the seeded_agent fixture; the rate-
limit test goes through the MCP HTTP path so the AuthMiddleware actually fires.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ClientError, ToolError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import async_session_factory
from app.main import app
from app.mcp.errors import (
    InvalidProbabilitiesError,
    MatchCancelledError,
    MatchNotFoundError,
    MatchTeamsTbdError,
    PredictionLockedError,
)
from app.mcp.tools.predictions import get_my_predictions, submit_prediction

pytestmark = pytest.mark.usefixtures("clean_humans")

GROUP_MATCH_ID = 1


async def test_tool_submit_then_get_my_predictions(seeded_agent) -> None:
    _agent, _ = seeded_agent
    result = await submit_prediction(
        match_id=GROUP_MATCH_ID,
        p_home=0.65,
        p_draw=0.20,
        p_away=0.15,
        pred_home_goals=2,
        pred_away_goals=0,
        reasoning="opener pick",
    )
    assert result["ok"] is True
    assert result["is_update"] is False
    assert result["match_id"] == GROUP_MATCH_ID

    mine = await get_my_predictions(limit=10)
    assert len(mine["predictions"]) == 1
    row = mine["predictions"][0]
    assert row["match_id"] == GROUP_MATCH_ID
    assert row["reasoning"] == "opener pick"
    assert row["pred_home_goals"] == 2


async def test_tool_resubmit_marks_is_update(seeded_agent) -> None:
    _agent, _ = seeded_agent
    first = await submit_prediction(
        match_id=GROUP_MATCH_ID, p_home=0.65, p_draw=0.20, p_away=0.15
    )
    second = await submit_prediction(
        match_id=GROUP_MATCH_ID, p_home=0.5, p_draw=0.3, p_away=0.2
    )
    assert first["is_update"] is False
    assert second["is_update"] is True
    # the latest write is what `get_my_predictions` returns
    mine = await get_my_predictions(limit=10)
    assert mine["predictions"][0]["p_home"] == 0.5


async def test_tool_invalid_probabilities(seeded_agent) -> None:
    _agent, _ = seeded_agent
    with pytest.raises(InvalidProbabilitiesError):
        await submit_prediction(match_id=GROUP_MATCH_ID, p_home=0.6, p_draw=0.6, p_away=0.3)


async def test_tool_match_not_found(seeded_agent) -> None:
    _agent, _ = seeded_agent
    with pytest.raises(MatchNotFoundError):
        await submit_prediction(match_id=99999, p_home=0.5, p_draw=0.3, p_away=0.2)


async def test_tool_match_teams_tbd(seeded_agent) -> None:
    _agent, _ = seeded_agent
    with pytest.raises(MatchTeamsTbdError):
        await submit_prediction(match_id=104, p_home=0.5, p_draw=0.3, p_away=0.2)


async def test_tool_match_cancelled(seeded_agent) -> None:
    _agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET status = 'cancelled' WHERE id = :id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        with pytest.raises(MatchCancelledError):
            await submit_prediction(
                match_id=GROUP_MATCH_ID, p_home=0.5, p_draw=0.3, p_away=0.2
            )
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text("UPDATE matches SET status = 'scheduled' WHERE id = :id"),
                {"id": GROUP_MATCH_ID},
            )


async def test_tool_prediction_locked(seeded_agent) -> None:
    _agent, _ = seeded_agent
    async with async_session_factory() as db, db.begin():
        await db.execute(
            text("UPDATE matches SET lock_at = now() - interval '1 hour' WHERE id = :id"),
            {"id": GROUP_MATCH_ID},
        )
    try:
        with pytest.raises(PredictionLockedError):
            await submit_prediction(
                match_id=GROUP_MATCH_ID, p_home=0.5, p_draw=0.3, p_away=0.2
            )
    finally:
        async with async_session_factory() as db, db.begin():
            await db.execute(
                text(
                    "UPDATE matches SET lock_at = kickoff_at - interval '1 hour'"
                    " WHERE id = :id"
                ),
                {"id": GROUP_MATCH_ID},
            )


def _make_transport(headers: dict[str, str]) -> StreamableHttpTransport:
    def factory(**kwargs: Any) -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            **kwargs,
        )

    return StreamableHttpTransport(
        url="http://testserver/mcp/",
        headers=headers,
        httpx_client_factory=factory,
    )


@pytest.mark.usefixtures("app_lifespan")
async def test_per_agent_rate_limit_61st_call_429(seeded_agent) -> None:
    """60 calls per minute per agent across all tools. 61st must surface as
    RATE_LIMITED through the MCP middleware."""
    _agent, token = seeded_agent
    transport = _make_transport({"Authorization": f"Bearer {token}"})
    async with Client(transport) as mcp_client:
        # 60 cheap reads should all succeed
        for _ in range(60):
            await mcp_client.call_tool("list_teams", {})
        with pytest.raises((ToolError, ClientError)) as excinfo:
            await mcp_client.call_tool("list_teams", {})
    msg = str(excinfo.value).lower()
    assert "rate" in msg or "limit" in msg
