"""`/api/v1/auth/*` — endpoints called by Auth.js on sign-in."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.api.deps import get_db, get_id_token_verifier
from app.api.rate_limit import limiter
from app.api.schemas.auth import VerifyRequest, VerifyResponse
from app.db.models.agent import Agent
from app.domain.auth_service import IdTokenVerifier, verify_and_upsert

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/verify", response_model=VerifyResponse)
@limiter.limit("5/minute")
async def verify(
    request: Request,
    body: VerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    verifier: Annotated[IdTokenVerifier, Depends(get_id_token_verifier)],
) -> VerifyResponse:
    """Verify a Google ID token and upsert the corresponding human row."""
    result = await verify_and_upsert(
        db,
        body.id_token,
        verifier=verifier,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    has_agent = (
        await db.scalar(select(Agent.id).where(Agent.human_id == result.human.id))
        is not None
    )
    return VerifyResponse(
        human_id=result.human.id,
        email=result.human.email,
        name=result.human.name,
        avatar_url=result.human.avatar_url,
        is_admin=result.human.is_admin,
        has_agent=has_agent,
        created=result.created,
    )
