"""Google ID token verification + humans upsert.

Verification uses google-auth, which checks signature, expiry, issuer, and audience
against the configured `GOOGLE_OAUTH_CLIENT_ID`. We never trust an unverified token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.audit import write_audit
from app.db.models.human import Human
from app.lib.disposable_domains import is_disposable
from app.lib.errors import BlockedDomainError, InvalidTokenError


class IdTokenVerifier(Protocol):
    """Indirection so tests can inject a fake verifier without hitting Google."""

    def __call__(self, token: str, client_id: str) -> dict[str, Any]: ...


def google_verifier(token: str, client_id: str) -> dict[str, Any]:
    """Default verifier: hits Google to validate the token.

    `verify_oauth2_token` raises ValueError on any signature/audience/expiry mismatch.
    """
    return google_id_token.verify_oauth2_token(  # type: ignore[no-any-return]
        token, google_requests.Request(), client_id
    )


@dataclass(frozen=True, slots=True)
class VerifyResult:
    human: Human
    created: bool


async def verify_and_upsert(
    db: AsyncSession,
    id_token: str,
    *,
    verifier: IdTokenVerifier,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> VerifyResult:
    """Verify a Google ID token and upsert the corresponding `humans` row.

    Raises:
        InvalidTokenError: token signature/expiry/audience mismatch or missing claims.
        BlockedDomainError: email domain is on the disposable list.
    """
    if not settings.google_oauth_client_id:
        # Misconfigured deploy. Surface clearly instead of silently failing.
        raise InvalidTokenError("server missing google_oauth_client_id")

    try:
        claims = verifier(id_token, settings.google_oauth_client_id)
    except ValueError as exc:
        raise InvalidTokenError(str(exc)) from exc

    sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified", False)
    if not isinstance(sub, str) or not isinstance(email, str) or not email_verified:
        raise InvalidTokenError("missing or unverified email claim")

    email_lc = email.lower()
    if is_disposable(email_lc):
        raise BlockedDomainError("disposable email domain")

    name = claims.get("name") if isinstance(claims.get("name"), str) else None
    picture = claims.get("picture") if isinstance(claims.get("picture"), str) else None
    should_be_admin = email_lc in settings.admin_email_set

    human = await db.scalar(select(Human).where(Human.google_sub == sub))
    created = False
    if human is None:
        # Fall back to email-match (older signup with a different google_sub linkage).
        human = await db.scalar(select(Human).where(Human.email == email_lc))

    if human is None:
        human = Human(
            google_sub=sub,
            email=email_lc,
            name=name,
            avatar_url=picture,
            is_admin=should_be_admin,
        )
        db.add(human)
        await db.flush()
        created = True
        await write_audit(
            db,
            actor_type="human",
            actor_id=human.id,
            action="signup",
            target_type="human",
            target_id=str(human.id),
            metadata={"email": email_lc},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    else:
        # Refresh profile fields that Google may have updated.
        human.google_sub = sub
        human.email = email_lc
        if name is not None:
            human.name = name
        if picture is not None:
            human.avatar_url = picture
        if should_be_admin and not human.is_admin:
            human.is_admin = True

    return VerifyResult(human=human, created=created)
