"""Shared serializers used by the read-only MCP tools.

Mirrors `docs/04-mcp-spec.md` field shapes. Keeps tool functions tiny and avoids
N+1 by always loading teams via `selectinload`.
"""

from __future__ import annotations

from typing import Any

from app.db.models.match import Match
from app.db.models.team import Team


def team_brief(team: Team | None, fallback_placeholder: str | None) -> dict[str, Any] | None:
    if team is not None:
        return {
            "team_id": team.id,
            "code": team.fifa_code,
            "name": team.name_en,
            "flag": team.flag_emoji,
        }
    if fallback_placeholder:
        return {"team_id": None, "code": None, "name": fallback_placeholder, "flag": None}
    return None


def team_full(team: Team) -> dict[str, Any]:
    return {
        "team_id": team.id,
        "code": team.fifa_code,
        "name_en": team.name_en,
        "name_es": team.name_es,
        "flag": team.flag_emoji,
        "group_letter": team.group_letter,
        "confederation": team.confederation,
    }


def venue(match: Match) -> str | None:
    if match.venue_city and match.venue_country:
        return f"{match.venue_city}, {match.venue_country}"
    return match.venue_city or match.venue_country


def match_core(match: Match) -> dict[str, Any]:
    return {
        "match_id": match.id,
        "stage": match.stage,
        "group_letter": match.group_letter,
        "home": team_brief(match.home_team, match.home_placeholder),
        "away": team_brief(match.away_team, match.away_placeholder),
        "kickoff_at": match.kickoff_at.isoformat(),
        "lock_at": match.lock_at.isoformat(),
        "venue": venue(match),
        "status": match.status,
    }


def match_result(match: Match) -> dict[str, Any] | None:
    if match.status != "finished" or match.home_goals is None or match.away_goals is None:
        return None
    outcome = "H" if match.home_goals > match.away_goals else "A" if match.home_goals < match.away_goals else "D"
    if match.went_to_penalties and outcome == "D":
        outcome = (
            "H"
            if (match.penalties_home or 0) > (match.penalties_away or 0)
            else "A"
        )
    return {
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "went_to_penalties": match.went_to_penalties,
        "penalties_home": match.penalties_home,
        "penalties_away": match.penalties_away,
        "outcome": outcome,
    }
