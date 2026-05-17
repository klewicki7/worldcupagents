"""Tool-level tests for the M3 read-only MCP tools.

Calls tool functions directly with a `current_agent` bound by the
`seeded_agent` fixture, so the bearer-token middleware doesn't need to fire.
The middleware itself is covered separately in `test_mcp_http.py`.
"""

from __future__ import annotations

import pytest

from app.mcp.errors import (
    AgentNotFoundError,
    InvalidParamError,
    MatchNotFoundError,
)
from app.mcp.tools.matches import (
    get_match,
    list_finished_matches,
    list_upcoming_matches,
)
from app.mcp.tools.predictions import get_my_predictions
from app.mcp.tools.scores import (
    get_agent_profile,
    get_leaderboard,
    get_my_score,
)
from app.mcp.tools.teams import list_teams

pytestmark = pytest.mark.usefixtures("clean_humans")


async def test_list_upcoming_matches_returns_seeded_fixtures(seeded_agent) -> None:
    _ = seeded_agent
    result = await list_upcoming_matches(limit=5)
    assert "matches" in result
    assert len(result["matches"]) == 5
    # Sorted ascending by kickoff_at: first match is the opener
    first = result["matches"][0]
    assert first["status"] == "scheduled"
    assert first["your_prediction"] is None


async def test_list_upcoming_matches_filter_by_stage(seeded_agent) -> None:
    _ = seeded_agent
    result = await list_upcoming_matches(limit=100, stage="final")
    assert len(result["matches"]) == 1
    assert result["matches"][0]["stage"] == "final"


async def test_list_upcoming_matches_filter_by_team(seeded_agent) -> None:
    _ = seeded_agent
    result = await list_upcoming_matches(limit=10, team_code="ARG")
    assert len(result["matches"]) >= 1
    for m in result["matches"]:
        codes = {m["home"]["code"], m["away"]["code"]}
        assert "ARG" in codes


async def test_list_upcoming_matches_unknown_team_raises(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await list_upcoming_matches(team_code="ZZZ")


async def test_list_upcoming_matches_caps_limit(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await list_upcoming_matches(limit=0)


async def test_list_finished_matches_empty_at_m3(seeded_agent) -> None:
    """No matches are resolved yet at M3 — empty list is the legitimate shape."""
    _ = seeded_agent
    result = await list_finished_matches()
    assert result["matches"] == []


async def test_list_finished_matches_bad_since_raises(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await list_finished_matches(since="not-a-date")


async def test_get_match_returns_existing_fixture(seeded_agent) -> None:
    _ = seeded_agent
    result = await get_match(match_id=1)
    assert result["match_id"] == 1
    assert result["home"] is not None
    assert result["away"] is not None
    assert result["result"] is None  # unfinished


async def test_get_match_unknown_id_raises(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(MatchNotFoundError):
        await get_match(match_id=99999)


async def test_list_teams_returns_all_48(seeded_agent) -> None:
    _ = seeded_agent
    result = await list_teams()
    assert len(result["teams"]) == 48


async def test_list_teams_filter_by_group(seeded_agent) -> None:
    _ = seeded_agent
    result = await list_teams(group_letter="a")  # lower-case → normalized
    assert len(result["teams"]) == 4
    assert all(t["group_letter"] == "A" for t in result["teams"])


async def test_list_teams_invalid_group(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await list_teams(group_letter="abc")


async def test_get_my_predictions_empty(seeded_agent) -> None:
    _ = seeded_agent
    result = await get_my_predictions()
    assert result["predictions"] == []


async def test_get_my_predictions_filters_mutex(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await get_my_predictions(only_open=True, only_finished=True)


async def test_get_my_score_empty_shape(seeded_agent) -> None:
    agent, _ = seeded_agent
    result = await get_my_score()
    assert result["agent_id"] == str(agent.id)
    assert result["matches_predicted"] == 0
    assert result["avg_brier"] is None
    assert result["total_exact_pts"] == 0
    assert result["rank"] is None  # below the min_matches=3 threshold


async def test_get_leaderboard_empty(seeded_agent) -> None:
    _ = seeded_agent
    result = await get_leaderboard()
    assert result["leaderboard"] == []
    assert result["total_agents"] == 0


async def test_get_leaderboard_rejects_bad_offset(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(InvalidParamError):
        await get_leaderboard(offset=-1)


async def test_get_agent_profile_by_slug(seeded_agent) -> None:
    agent, _ = seeded_agent
    result = await get_agent_profile(agent.slug)
    assert result["agent_id"] == str(agent.id)
    assert result["slug"] == agent.slug
    assert result["recent_predictions"] == []


async def test_get_agent_profile_by_uuid(seeded_agent) -> None:
    agent, _ = seeded_agent
    result = await get_agent_profile(str(agent.id))
    assert result["agent_id"] == str(agent.id)


async def test_get_agent_profile_unknown_raises(seeded_agent) -> None:
    _ = seeded_agent
    with pytest.raises(AgentNotFoundError):
        await get_agent_profile("not-a-real-slug")
