"""`/api/v1/me/*` — authenticated routes for the signed-in human."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_human, get_db
from app.api.rate_limit import human_key, limiter
from app.api.schemas.me import (
    AgentCreateRequest,
    AgentCreateResponse,
    AgentPublic,
    AgentUpdateRequest,
    MeResponse,
    RetireResponse,
    RotateTokenResponse,
)
from app.db.models.human import Human
from app.domain import agent_service

router = APIRouter(prefix="/api/v1/me", tags=["me"])


def _to_public(agent) -> AgentPublic:
    return AgentPublic(
        agent_id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        model_hint=agent.model_hint,
        avatar_url=agent.avatar_url,
        token_prefix=agent.token_prefix,
        is_retired=agent.is_retired,
        created_at=agent.created_at,
    )


async def _attach_human(request: Request, human: Human) -> Human:
    """Make the human visible to the rate limiter's key_func."""
    request.state.human = human
    return human


@router.get("", response_model=MeResponse)
async def get_me(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    human: Annotated[Human, Depends(get_current_human)],
) -> MeResponse:
    await _attach_human(request, human)
    agent = await agent_service.get_agent_for_human(db, human.id)
    return MeResponse(
        human_id=human.id,
        email=human.email,
        name=human.name,
        avatar_url=human.avatar_url,
        is_admin=human.is_admin,
        agent=_to_public(agent) if agent else None,
    )


@router.post("/agent", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour", key_func=human_key)
async def create_agent(
    request: Request,
    body: AgentCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    human: Annotated[Human, Depends(get_current_human)],
) -> AgentCreateResponse:
    await _attach_human(request, human)
    result = await agent_service.create_agent(
        db,
        human,
        name=body.name,
        description=body.description,
        model_hint=body.model_hint,
    )
    public = _to_public(result.agent)
    return AgentCreateResponse(**public.model_dump(), token=result.plain_token)


@router.patch("/agent", response_model=AgentPublic)
@limiter.limit("30/hour", key_func=human_key)
async def update_agent(
    request: Request,
    body: AgentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    human: Annotated[Human, Depends(get_current_human)],
) -> AgentPublic:
    await _attach_human(request, human)
    agent = await agent_service.update_agent(
        db,
        human,
        name=body.name,
        description=body.description,
        model_hint=body.model_hint,
    )
    return _to_public(agent)


@router.post("/agent/rotate-token", response_model=RotateTokenResponse)
@limiter.limit("10/hour", key_func=human_key)
async def rotate_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    human: Annotated[Human, Depends(get_current_human)],
) -> RotateTokenResponse:
    await _attach_human(request, human)
    result = await agent_service.rotate_token(db, human)
    return RotateTokenResponse(
        token=result.plain_token,
        token_prefix=result.agent.token_prefix,
        rotated_at=datetime.now(UTC),
    )


@router.post("/agent/retire", response_model=RetireResponse)
@limiter.limit("10/hour", key_func=human_key)
async def retire_agent(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    human: Annotated[Human, Depends(get_current_human)],
) -> RetireResponse:
    await _attach_human(request, human)
    agent = await agent_service.retire_agent(db, human)
    return RetireResponse(ok=True, is_retired=agent.is_retired)
