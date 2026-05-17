from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    id_token: str = Field(min_length=10)


class VerifyResponse(BaseModel):
    human_id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    is_admin: bool
    has_agent: bool
    created: bool
