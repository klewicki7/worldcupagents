"""FastAPI dependencies: DB session, current human (JWT auth), admin gate."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Header
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.human import Human
from app.db.session import async_session_factory
from app.lib.errors import ForbiddenError, UnauthenticatedError


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def _extract_token(
    authorization: str | None,
    session_cookie: str | None,
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if session_cookie:
        return session_cookie
    raise UnauthenticatedError("missing token")


async def get_current_human(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    next_auth_session_token: Annotated[
        str | None, Cookie(alias="next-auth.session-token")
    ] = None,
    secure_next_auth_session_token: Annotated[
        str | None, Cookie(alias="__Secure-next-auth.session-token")
    ] = None,
) -> Human:
    """Resolve the authenticated human from a JWT in Authorization header or Auth.js cookie.

    Cross-checks `humans.is_admin` against the DB rather than trusting the JWT claim.
    """
    token = _extract_token(authorization, next_auth_session_token or secure_next_auth_session_token)
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthenticatedError("invalid jwt") from exc

    sub = claims.get("sub")
    if not isinstance(sub, str):
        raise UnauthenticatedError("missing sub claim")
    try:
        human_id = UUID(sub)
    except ValueError as exc:
        raise UnauthenticatedError("sub is not a uuid") from exc

    human = await db.scalar(select(Human).where(Human.id == human_id))
    if human is None:
        raise UnauthenticatedError("human not found")
    return human


async def require_admin(
    human: Annotated[Human, Depends(get_current_human)],
) -> Human:
    if not human.is_admin:
        raise ForbiddenError("admin only")
    return human
