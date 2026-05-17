"""MCP tool: list_teams."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models.team import Team
from app.db.session import async_session_factory
from app.mcp.context import current_agent
from app.mcp.errors import InvalidParamError
from app.mcp.serialization import team_full


async def list_teams(group_letter: str | None = None) -> dict[str, Any]:
    """Return all 48 teams, optionally filtered by group letter (A..L)."""
    current_agent()
    if group_letter is not None:
        if len(group_letter) != 1 or not group_letter.isalpha():
            raise InvalidParamError("group_letter must be a single letter", {"group_letter": group_letter})
        group_letter = group_letter.upper()
    async with async_session_factory() as db:
        stmt = select(Team).order_by(Team.id.asc())
        if group_letter is not None:
            stmt = stmt.where(Team.group_letter == group_letter)
        rows = (await db.scalars(stmt)).all()
        return {"teams": [team_full(t) for t in rows]}
