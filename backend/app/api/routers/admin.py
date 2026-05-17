"""`/api/v1/admin/*` — match resolution + override.

Both routes are admin-gated by the `require_admin` dependency (which itself
re-checks `humans.is_admin` against the DB, never trusts the JWT alone).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.api.rate_limit import human_key, limiter
from app.api.schemas.admin import (
    OverrideRequest,
    OverrideResponse,
    ResolveRequest,
    ResolveResponse,
)
from app.db.models.human import Human
from app.domain import resolution_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/matches/{match_id}/resolve", response_model=ResolveResponse)
@limiter.limit("60/minute", key_func=human_key)
async def resolve_match(
    request: Request,
    match_id: int,
    body: ResolveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Human, Depends(require_admin)],
) -> ResolveResponse:
    request.state.human = admin
    result = await resolution_service.resolve_match(
        db,
        match_id=match_id,
        home_goals=body.home_goals,
        away_goals=body.away_goals,
        went_to_penalties=body.went_to_penalties,
        penalties_home=body.penalties_home,
        penalties_away=body.penalties_away,
        actor_human_id=admin.id,
    )
    return ResolveResponse(
        match_id=result.match_id,
        outcome=result.outcome,
        predictions_scored=result.predictions_scored,
        resolved_at=result.resolved_at,
    )


@router.post("/matches/{match_id}/override", response_model=OverrideResponse)
@limiter.limit("60/minute", key_func=human_key)
async def override_match(
    request: Request,
    match_id: int,
    body: OverrideRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Human, Depends(require_admin)],
) -> OverrideResponse:
    request.state.human = admin
    result = await resolution_service.override_match(
        db,
        match_id=match_id,
        home_goals=body.home_goals,
        away_goals=body.away_goals,
        went_to_penalties=body.went_to_penalties,
        penalties_home=body.penalties_home,
        penalties_away=body.penalties_away,
        actor_human_id=admin.id,
        reason=body.reason,
    )
    return OverrideResponse(
        match_id=result.match_id,
        old_outcome=result.old_outcome,
        new_outcome=result.new_outcome,
        predictions_rescored=result.predictions_rescored,
        overridden_at=result.overridden_at,
    )
