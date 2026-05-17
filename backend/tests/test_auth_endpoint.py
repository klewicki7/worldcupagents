"""POST /api/v1/auth/verify."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.db.models.human import Human
from app.db.session import async_session_factory
from tests.api_helpers import (
    FakeVerifier,
    clear_verifier,
    configure_test_settings,
    google_claims,
    install_verifier,
)

pytestmark = pytest.mark.usefixtures("clean_humans")


async def test_verify_creates_human(client: AsyncClient) -> None:
    configure_test_settings()
    install_verifier(
        FakeVerifier(
            {"good-token-aaaa": google_claims(sub="google-sub-1", email="kev@example.com", name="Kev")}
        )
    )
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "kev@example.com"
    assert body["created"] is True
    assert body["has_agent"] is False

    async with async_session_factory() as session:
        rows = (await session.scalars(select(Human))).all()
    assert len(rows) == 1
    assert rows[0].google_sub == "google-sub-1"


async def test_verify_is_idempotent(client: AsyncClient) -> None:
    configure_test_settings()
    install_verifier(
        FakeVerifier(
            {"good-token-aaaa": google_claims(sub="sub-A", email="a@example.com")}
        )
    )
    try:
        first = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
        second = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["human_id"] == second.json()["human_id"]


async def test_verify_assigns_admin_from_env(client: AsyncClient) -> None:
    configure_test_settings()
    settings.admin_emails = "boss@example.com,kev@example.com"
    install_verifier(
        FakeVerifier(
            {"good-token-aaaa": google_claims(sub="sub-admin", email="Boss@Example.com")}
        )
    )
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()
        settings.admin_emails = ""
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True


async def test_verify_rejects_invalid_token(client: AsyncClient) -> None:
    configure_test_settings()
    install_verifier(FakeVerifier({"bad-token-bbbb": ValueError("signature mismatch")}))
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "bad-token-bbbb"})
    finally:
        clear_verifier()
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_TOKEN"


async def test_verify_blocks_disposable_domain(client: AsyncClient) -> None:
    configure_test_settings()
    install_verifier(
        FakeVerifier(
            {"good-token-aaaa": google_claims(sub="sub-x", email="spammer@mailinator.com")}
        )
    )
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()
    assert resp.status_code == 400
    assert resp.json()["error"] == "BLOCKED_DOMAIN"


async def test_verify_rejects_unverified_email(client: AsyncClient) -> None:
    configure_test_settings()
    install_verifier(
        FakeVerifier(
            {
                "good-token-aaaa": google_claims(
                    sub="sub-y", email="kev@example.com", email_verified=False
                )
            }
        )
    )
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_TOKEN"


async def test_verify_rate_limit(client: AsyncClient) -> None:
    """5/minute/IP — the 6th hit returns 429."""
    configure_test_settings()
    install_verifier(
        FakeVerifier(
            {"good-token-aaaa": google_claims(sub="sub-rl", email="rl@example.com")}
        )
    )
    try:
        codes = [
            (await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})).status_code
            for _ in range(6)
        ]
    finally:
        clear_verifier()
    assert codes[:5] == [200, 200, 200, 200, 200]
    assert codes[5] == 429
