"""FastMCP middleware: bearer-token auth, structured logging."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.db.session import async_session_factory
from app.mcp.auth import resolve_agent
from app.mcp.context import reset_current_agent, set_current_agent
from app.mcp.errors import AgentRetiredError, InvalidTokenError, McpToolError

logger = logging.getLogger("app.mcp")


def _extract_bearer(headers: dict[str, str]) -> str | None:
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


class AuthMiddleware(Middleware):
    """Resolve Bearer → Agent and bind it to the current_agent contextvar."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: Callable[[MiddlewareContext[Any]], Awaitable[Any]],
    ) -> Any:
        headers = get_http_headers(include_all=True)
        token = _extract_bearer(headers)
        if token is None:
            raise InvalidTokenError("missing bearer token")

        async with async_session_factory() as session:
            agent = await resolve_agent(session, token)

        if agent.is_retired:
            raise AgentRetiredError()

        reset_token = set_current_agent(agent)
        try:
            return await call_next(context)
        finally:
            reset_current_agent(reset_token)


class LoggingMiddleware(Middleware):
    """Log tool name, agent_id (if bound), latency, and outcome on every call."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: Callable[[MiddlewareContext[Any]], Awaitable[Any]],
    ) -> Any:
        from app.mcp.context import _current_agent  # local to avoid import cycle at module load

        start = time.perf_counter()
        tool_name = getattr(context.message, "name", "?")
        agent = _current_agent.get()
        agent_id = str(agent.id) if agent is not None else None
        try:
            result = await call_next(context)
        except McpToolError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(
                "mcp_tool_call error tool=%s agent_id=%s code=%s latency_ms=%.1f",
                tool_name,
                agent_id,
                exc.code,
                elapsed,
            )
            raise
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "mcp_tool_call crash tool=%s agent_id=%s latency_ms=%.1f",
                tool_name,
                agent_id,
                elapsed,
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "mcp_tool_call ok tool=%s agent_id=%s latency_ms=%.1f",
            tool_name,
            agent_id,
            elapsed,
        )
        return result
