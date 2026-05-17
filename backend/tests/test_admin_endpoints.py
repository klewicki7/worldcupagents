"""HTTP tests for /api/v1/admin/matches/{id}/resolve + /override."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.human import Human
from app.db.models.score import Score
from app.db.session import async_session_factory
from tests.api_helpers import make_jwt

pytestmark = pytest.mark.usefixtures("clean_humans")

GROUP_MATCH_ID = 1


async def _seed_admin(email: str = "admin@example.com") -> Human:
    async with async_session_factory() as session, session.begin():
        human = Human(google_sub="admin-rest", email=email, is_admin=True)
        session.add(human)
        await session.flush()
        await session.refresh(human)
    return human


async def _seed_regular_human() -> Human:
    async with async_session_factory() as session, session.begin():
        human = Human(google_sub="regular-rest", email="regular@example.com")
        session.add(human)
        await session.flush()
        await session.refresh(human)
    return human


def _auth(jwt_value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt_value}"}


async def test_resolve_happy_path(client: AsyncClient) -> None:
    admin = await _seed_admin()
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 2, "away_goals": 1},
        headers=_auth(make_jwt(str(admin.id), is_admin=True)),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["match_id"] == GROUP_MATCH_ID
    assert body["outcome"] == "H"
    assert body["predictions_scored"] == 0  # no predictions seeded


async def test_resolve_requires_admin_403(client: AsyncClient) -> None:
    user = await _seed_regular_human()
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 1, "away_goals": 0},
        headers=_auth(make_jwt(str(user.id))),
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "FORBIDDEN"


async def test_resolve_requires_auth_401(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 1, "away_goals": 0},
    )
    assert resp.status_code == 401


async def test_resolve_unknown_match_404(client: AsyncClient) -> None:
    admin = await _seed_admin()
    resp = await client.post(
        "/api/v1/admin/matches/99999/resolve",
        json={"home_goals": 0, "away_goals": 0},
        headers=_auth(make_jwt(str(admin.id), is_admin=True)),
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "NOT_FOUND"


async def test_resolve_twice_returns_409(client: AsyncClient) -> None:
    admin = await _seed_admin()
    headers = _auth(make_jwt(str(admin.id), is_admin=True))
    first = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 2, "away_goals": 1},
        headers=headers,
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 2, "away_goals": 1},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"] == "ALREADY_RESOLVED"


async def test_resolve_invalid_negative_goals_400(client: AsyncClient) -> None:
    admin = await _seed_admin()
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": -1, "away_goals": 0},
        headers=_auth(make_jwt(str(admin.id), is_admin=True)),
    )
    assert resp.status_code == 422  # caught by pydantic Field(ge=0)


async def test_override_after_resolve(client: AsyncClient) -> None:
    admin = await _seed_admin()
    headers = _auth(make_jwt(str(admin.id), is_admin=True))
    await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 2, "away_goals": 1},
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/override",
        json={"home_goals": 1, "away_goals": 2, "reason": "recount"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["old_outcome"] == "H"
    assert body["new_outcome"] == "A"


async def test_override_before_resolve_returns_409(client: AsyncClient) -> None:
    admin = await _seed_admin()
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/override",
        json={"home_goals": 1, "away_goals": 0},
        headers=_auth(make_jwt(str(admin.id), is_admin=True)),
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "NOT_RESOLVED"


async def test_override_requires_admin_403(client: AsyncClient) -> None:
    user = await _seed_regular_human()
    resp = await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/override",
        json={"home_goals": 1, "away_goals": 0},
        headers=_auth(make_jwt(str(user.id))),
    )
    assert resp.status_code == 403


async def test_scores_persisted_after_resolve(client: AsyncClient) -> None:
    """Smoke through to the scores table."""
    admin = await _seed_admin()
    await client.post(
        f"/api/v1/admin/matches/{GROUP_MATCH_ID}/resolve",
        json={"home_goals": 2, "away_goals": 1},
        headers=_auth(make_jwt(str(admin.id), is_admin=True)),
    )
    # No predictions seeded → no scores either.
    async with async_session_factory() as db:
        rows = (await db.scalars(select(Score))).all()
    assert rows == []
