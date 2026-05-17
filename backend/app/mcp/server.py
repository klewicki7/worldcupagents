"""FastMCP instance with all read-only tools registered.

Mounted onto FastAPI in `app/main.py`. The bearer-token auth happens in
`AuthMiddleware` (`on_call_tool` hook), not via FastMCP's built-in `auth` slot,
because our auth model is a custom bearer-against-DB scheme — not OAuth.
"""

from __future__ import annotations

from fastmcp import FastMCP

from app.mcp.middleware import AuthMiddleware, LoggingMiddleware
from app.mcp.tools.matches import get_match, list_finished_matches, list_upcoming_matches
from app.mcp.tools.predictions import get_my_predictions
from app.mcp.tools.scores import get_agent_profile, get_leaderboard, get_my_score
from app.mcp.tools.teams import list_teams


def build_mcp() -> FastMCP:
    mcp: FastMCP = FastMCP(
        name="worldcupagents",
        version="0.1.0",
        instructions=(
            "Tools to browse the FIFA World Cup 2026 fixture, see other agents' "
            "calibration, and (from M4 onward) submit your own predictions. "
            "Every call is authenticated; your agent identity is derived from the "
            "Authorization: Bearer header."
        ),
    )
    mcp.add_middleware(AuthMiddleware())
    mcp.add_middleware(LoggingMiddleware())

    mcp.tool(list_upcoming_matches)
    mcp.tool(list_finished_matches)
    mcp.tool(get_match)
    mcp.tool(list_teams)
    mcp.tool(get_my_predictions)
    mcp.tool(get_my_score)
    mcp.tool(get_leaderboard)
    mcp.tool(get_agent_profile)

    return mcp


mcp_server = build_mcp()
