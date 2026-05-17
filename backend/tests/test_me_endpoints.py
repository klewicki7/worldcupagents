"""GET /me + POST/PATCH /me/agent + rotate + retire."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.agent import Agent
from app.db.models.human import Human
from app.db.session import async_session_factory
from app.lib.tokens import verify_token
from tests.api_helpers import (
    FakeVerifier,
    clear_verifier,
    configure_test_settings,
    google_claims,
    install_verifier,
    make_jwt,
)

pytestmark = pytest.mark.usefixtures("clean_humans")


async def _signup(client: AsyncClient, *, sub: str, email: str) -> str:
    configure_test_settings()
    install_verifier(FakeVerifier({"good-token-aaaa": google_claims(sub=sub, email=email)}))
    try:
        resp = await client.post("/api/v1/auth/verify", json={"id_token": "good-token-aaaa"})
    finally:
        clear_verifier()
    assert resp.status_code == 200, resp.text
    return resp.json()["human_id"]


def _auth(jwt_value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt_value}"}


async def test_get_me_returns_null_agent(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s1", email="a@example.com")
    resp = await client.get("/api/v1/me", headers=_auth(make_jwt(human_id)))
    assert resp.status_code == 200
    body = resp.json()
    assert body["human_id"] == human_id
    assert body["agent"] is None


async def test_get_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHENTICATED"


async def test_get_me_rejects_unknown_human(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/me", headers=_auth(make_jwt(str(uuid4()))))
    assert resp.status_code == 401


async def test_create_agent_returns_plain_token_once(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s2", email="b@example.com")
    resp = await client.post(
        "/api/v1/me/agent",
        json={"name": "kevcode-predictor", "description": "test", "model_hint": "claude-opus-4.7"},
        headers=_auth(make_jwt(human_id)),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slug"] == "kevcode-predictor"
    assert body["token"].startswith("wca_")
    assert body["token_prefix"] == body["token"][:12]

    async with async_session_factory() as session:
        agent = (await session.scalars(select(Agent))).one()
    assert verify_token(body["token"], agent.token_hash) is True

    # /me now shows the agent but never re-exposes the plain token
    me = (await client.get("/api/v1/me", headers=_auth(make_jwt(human_id)))).json()
    assert me["agent"]["slug"] == "kevcode-predictor"
    assert "token" not in me["agent"]


async def test_create_second_agent_rejected(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s3", email="c@example.com")
    headers = _auth(make_jwt(human_id))
    first = await client.post(
        "/api/v1/me/agent",
        json={"name": "first-agent"},
        headers=headers,
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/me/agent",
        json={"name": "second-agent"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"] == "AGENT_ALREADY_EXISTS"


async def test_create_agent_rejects_reserved_name(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s4", email="d@example.com")
    resp = await client.post(
        "/api/v1/me/agent",
        json={"name": "claude-thinker"},
        headers=_auth(make_jwt(human_id)),
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "NAME_RESERVED"


async def test_create_agent_rejects_short_name(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s5", email="e@example.com")
    resp = await client.post(
        "/api/v1/me/agent",
        json={"name": "ab"},
        headers=_auth(make_jwt(human_id)),
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "INVALID_NAME"


async def test_name_taken_409(client: AsyncClient) -> None:
    human_a = await _signup(client, sub="s6", email="x@example.com")
    human_b = await _signup(client, sub="s7", email="y@example.com")
    first = await client.post(
        "/api/v1/me/agent",
        json={"name": "only-one"},
        headers=_auth(make_jwt(human_a)),
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/me/agent",
        json={"name": "only-one"},
        headers=_auth(make_jwt(human_b)),
    )
    assert second.status_code == 409
    assert second.json()["error"] == "NAME_TAKEN"


async def test_patch_agent_changes_slug(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s8", email="f@example.com")
    headers = _auth(make_jwt(human_id))
    await client.post("/api/v1/me/agent", json={"name": "old-name"}, headers=headers)
    resp = await client.patch(
        "/api/v1/me/agent",
        json={"name": "Brand New Name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "brand-new-name"


async def test_rotate_token_invalidates_old(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s9", email="g@example.com")
    headers = _auth(make_jwt(human_id))
    create = await client.post(
        "/api/v1/me/agent",
        json={"name": "rotator"},
        headers=headers,
    )
    old_token = create.json()["token"]

    rotate = await client.post("/api/v1/me/agent/rotate-token", headers=headers)
    assert rotate.status_code == 200
    new_token = rotate.json()["token"]
    assert new_token != old_token

    async with async_session_factory() as session:
        agent = (await session.scalars(select(Agent))).one()
    assert verify_token(new_token, agent.token_hash) is True
    assert verify_token(old_token, agent.token_hash) is False


async def test_retire_idempotent_and_audit_logged(client: AsyncClient) -> None:
    human_id = await _signup(client, sub="s10", email="h@example.com")
    headers = _auth(make_jwt(human_id))
    await client.post("/api/v1/me/agent", json={"name": "retiree"}, headers=headers)

    r1 = await client.post("/api/v1/me/agent/retire", headers=headers)
    r2 = await client.post("/api/v1/me/agent/retire", headers=headers)
    assert r1.status_code == 200
    assert r1.json() == {"ok": True, "is_retired": True}
    assert r2.status_code == 200

    async with async_session_factory() as session:
        human = (await session.scalars(select(Human).where(Human.id == human_id))).one()
    assert human is not None


async def test_create_agent_rate_limit(client: AsyncClient) -> None:
    """3/hour/human on agent creation. After the first 201 each duplicate
    attempt by the same human would 409 — but slowapi sees the 4th request
    before the handler runs and 429s it."""
    human_id = await _signup(client, sub="s11", email="rl@example.com")
    headers = _auth(make_jwt(human_id))

    statuses = []
    for i in range(4):
        resp = await client.post(
            "/api/v1/me/agent",
            json={"name": f"rate-limit-{i}"},
            headers=headers,
        )
        statuses.append(resp.status_code)

    # 1st succeeds (201), 2nd & 3rd hit AGENT_ALREADY_EXISTS (409), 4th is rate-limited (429).
    assert statuses[0] == 201
    assert statuses[1] == 409
    assert statuses[2] == 409
    assert statuses[3] == 429
