"""Shared helpers for API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from app.api.deps import get_id_token_verifier
from app.config import settings
from app.main import app


def make_jwt(human_id: str, *, email: str = "test@example.com", is_admin: bool = False) -> str:
    """Mint a JWT matching the Auth.js shape."""
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": human_id,
        "email": email,
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def google_claims(
    *,
    sub: str,
    email: str,
    name: str = "Test User",
    picture: str = "https://example.com/p.png",
    email_verified: bool = True,
) -> dict[str, Any]:
    return {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": picture,
    }


class FakeVerifier:
    """Replaces the Google ID token verifier. Maps token strings → claim dicts."""

    def __init__(self, claims_by_token: dict[str, dict[str, Any] | Exception]) -> None:
        self._table = claims_by_token

    def __call__(self, token: str, client_id: str) -> dict[str, Any]:
        result = self._table.get(token)
        if result is None:
            raise ValueError("unknown test token")
        if isinstance(result, Exception):
            raise result
        return result


def install_verifier(verifier: FakeVerifier) -> None:
    """Wire the fake verifier as a FastAPI dependency override."""
    app.dependency_overrides[get_id_token_verifier] = lambda: verifier


def clear_verifier() -> None:
    app.dependency_overrides.pop(get_id_token_verifier, None)


def configure_test_settings() -> None:
    """Sane settings for API tests."""
    settings.google_oauth_client_id = "test-client-id"
