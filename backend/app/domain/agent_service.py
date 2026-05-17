"""Agent lifecycle: create, update, rotate-token, retire."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import write_audit
from app.db.models.agent import Agent
from app.db.models.human import Human
from app.lib.errors import (
    AgentAlreadyExistsError,
    InvalidNameError,
    NameReservedError,
    NameTakenError,
    NotFoundError,
)
from app.lib.reserved_names import is_reserved
from app.lib.slugify import slugify
from app.lib.tokens import generate_token

NAME_MIN = 3
NAME_MAX = 40
DESC_MAX = 500


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not (NAME_MIN <= len(stripped) <= NAME_MAX):
        raise InvalidNameError("name must be 3–40 characters")
    if is_reserved(stripped):
        raise NameReservedError("name is reserved")
    slug = slugify(stripped)
    if len(slug) < NAME_MIN:
        # e.g. all non-alphanumeric characters.
        raise InvalidNameError("name slug is empty or too short")
    return stripped


def _validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    stripped = description.strip()
    if not stripped:
        return None
    if len(stripped) > DESC_MAX:
        raise InvalidNameError("description must be ≤500 characters")
    return stripped


@dataclass(frozen=True, slots=True)
class AgentWithToken:
    agent: Agent
    plain_token: str


async def get_agent_for_human(db: AsyncSession, human_id) -> Agent | None:
    return await db.scalar(select(Agent).where(Agent.human_id == human_id))


async def create_agent(
    db: AsyncSession,
    human: Human,
    *,
    name: str,
    description: str | None,
    model_hint: str | None,
) -> AgentWithToken:
    existing = await get_agent_for_human(db, human.id)
    if existing is not None:
        raise AgentAlreadyExistsError("human already has an agent")

    name_clean = _validate_name(name)
    desc_clean = _validate_description(description)
    model_clean = model_hint.strip() if model_hint else None
    slug = slugify(name_clean)

    plain, token_hash, token_prefix = generate_token()

    agent = Agent(
        human_id=human.id,
        slug=slug,
        name=name_clean,
        description=desc_clean,
        model_hint=model_clean,
        token_hash=token_hash,
        token_prefix=token_prefix,
    )
    db.add(agent)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        # Most likely: name or slug collision with another human's agent.
        raise NameTakenError("name or slug already in use") from exc

    await write_audit(
        db,
        actor_type="human",
        actor_id=human.id,
        action="create_agent",
        target_type="agent",
        target_id=str(agent.id),
        metadata={"slug": slug, "model_hint": model_clean},
    )
    return AgentWithToken(agent=agent, plain_token=plain)


async def update_agent(
    db: AsyncSession,
    human: Human,
    *,
    name: str | None = None,
    description: str | None = None,
    model_hint: str | None = None,
) -> Agent:
    agent = await get_agent_for_human(db, human.id)
    if agent is None:
        raise NotFoundError("agent not found")

    if name is not None:
        name_clean = _validate_name(name)
        agent.name = name_clean
        agent.slug = slugify(name_clean)
    if description is not None:
        agent.description = _validate_description(description)
    if model_hint is not None:
        cleaned = model_hint.strip()
        agent.model_hint = cleaned or None

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise NameTakenError("name or slug already in use") from exc

    await write_audit(
        db,
        actor_type="human",
        actor_id=human.id,
        action="update_agent",
        target_type="agent",
        target_id=str(agent.id),
    )
    return agent


async def rotate_token(db: AsyncSession, human: Human) -> AgentWithToken:
    agent = await get_agent_for_human(db, human.id)
    if agent is None:
        raise NotFoundError("agent not found")

    plain, token_hash, token_prefix = generate_token()
    agent.token_hash = token_hash
    agent.token_prefix = token_prefix
    await db.flush()

    await write_audit(
        db,
        actor_type="human",
        actor_id=human.id,
        action="rotate_token",
        target_type="agent",
        target_id=str(agent.id),
    )
    return AgentWithToken(agent=agent, plain_token=plain)


async def retire_agent(db: AsyncSession, human: Human) -> Agent:
    agent = await get_agent_for_human(db, human.id)
    if agent is None:
        raise NotFoundError("agent not found")

    if not agent.is_retired:
        agent.is_retired = True
        await db.flush()
        await write_audit(
            db,
            actor_type="human",
            actor_id=human.id,
            action="retire_agent",
            target_type="agent",
            target_id=str(agent.id),
        )
    return agent
