"""Per-request `current_agent` contextvar populated by the auth middleware."""

from __future__ import annotations

from contextvars import ContextVar

from app.db.models.agent import Agent
from app.mcp.errors import InvalidTokenError

_current_agent: ContextVar[Agent | None] = ContextVar("mcp_current_agent", default=None)


def set_current_agent(agent: Agent | None) -> object:
    """Returns a reset token. Pass it to `reset_current_agent`."""
    return _current_agent.set(agent)


def reset_current_agent(token: object) -> None:
    _current_agent.reset(token)  # type: ignore[arg-type]


def current_agent() -> Agent:
    """Get the agent bound to this MCP request. Raises if missing."""
    agent = _current_agent.get()
    if agent is None:
        raise InvalidTokenError("no agent bound to request")
    return agent
