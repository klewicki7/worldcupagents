from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentPublic(BaseModel):
    agent_id: UUID
    slug: str
    name: str
    description: str | None
    model_hint: str | None
    avatar_url: str | None
    token_prefix: str
    is_retired: bool
    created_at: datetime


class MeResponse(BaseModel):
    human_id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    is_admin: bool
    agent: AgentPublic | None


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    model_hint: str | None = Field(default=None, max_length=80)


class AgentCreateResponse(AgentPublic):
    token: str


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    model_hint: str | None = Field(default=None, max_length=80)


class RotateTokenResponse(BaseModel):
    token: str
    token_prefix: str
    rotated_at: datetime


class RetireResponse(BaseModel):
    ok: bool = True
    is_retired: bool = True
