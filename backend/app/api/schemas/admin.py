from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    home_goals: int = Field(ge=0, le=30)
    away_goals: int = Field(ge=0, le=30)
    went_to_penalties: bool = False
    penalties_home: int | None = Field(default=None, ge=0, le=30)
    penalties_away: int | None = Field(default=None, ge=0, le=30)


class ResolveResponse(BaseModel):
    match_id: int
    status: str = "finished"
    outcome: str
    predictions_scored: int
    resolved_at: datetime


class OverrideRequest(ResolveRequest):
    reason: str | None = Field(default=None, max_length=500)


class OverrideResponse(BaseModel):
    match_id: int
    old_outcome: str | None
    new_outcome: str
    predictions_rescored: int
    overridden_at: datetime
