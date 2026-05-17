"""End-to-end MCP HTTP tests: bearer-token auth via the FastAPI mount.

Uses the FastMCP Client with a `StreamableHttpTransport` whose underlying
httpx.AsyncClient is wired to an ASGITransport against the FastAPI app — so
real MCP JSON-RPC messages go through the middleware stack without binding a
TCP port. Also verifies retired agents are rejected.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ClientError, ToolError
from httpx import ASGITransport, AsyncClient

from app.db.models.agent import Agent
from app.db.session import async_session_factory
from app.main import app


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


pytestmark = pytest.mark.usefixtures("clean_humans", "app_lifespan")


async def test_valid_bearer_calls_tool(seeded_agent) -> None:
    _agent, token = seeded_agent
    transport = _make_transport({"Authorization": f"Bearer {token}"})
    async with Client(transport) as mcp_client:
        result = await mcp_client.call_tool("list_teams", {})
    payload = result.data
    assert isinstance(payload, dict)
    assert len(payload["teams"]) == 48


async def test_missing_bearer_returns_error(seeded_agent) -> None:
    _agent, _token = seeded_agent
    transport = _make_transport({})
    async with Client(transport) as mcp_client:
        with pytest.raises((ToolError, ClientError)) as excinfo:
            await mcp_client.call_tool("list_teams", {})
    msg = str(excinfo.value).lower()
    assert "bearer" in msg or "invalid" in msg


async def test_garbage_bearer_returns_error(seeded_agent) -> None:
    _agent, _token = seeded_agent
    transport = _make_transport({"Authorization": "Bearer wca_garbage_token_value"})
    async with Client(transport) as mcp_client:
        with pytest.raises((ToolError, ClientError)) as excinfo:
            await mcp_client.call_tool("list_teams", {})
    msg = str(excinfo.value).lower()
    assert "invalid" in msg or "bearer" in msg


async def test_retired_agent_blocked(seeded_agent) -> None:
    agent, token = seeded_agent
    async with async_session_factory() as session, session.begin():
        db_agent = await session.get(Agent, agent.id)
        assert db_agent is not None
        db_agent.is_retired = True

    transport = _make_transport({"Authorization": f"Bearer {token}"})
    async with Client(transport) as mcp_client:
        with pytest.raises((ToolError, ClientError)) as excinfo:
            await mcp_client.call_tool("list_teams", {})
    assert "AGENT_RETIRED" in str(excinfo.value) or "retired" in str(excinfo.value).lower()
