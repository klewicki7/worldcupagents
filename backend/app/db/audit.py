"""Audit log helper. Every meaningful write should go through this."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    actor_type: str,
    action: str,
    actor_id: UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Insert one audit row. Caller is responsible for committing the surrounding tx."""
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        audit_metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
