from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    human_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("humans.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    model_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String, nullable=False)
    is_retired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(name) BETWEEN 3 AND 40", name="name_length"
        ),
        CheckConstraint(
            "description IS NULL OR char_length(description) <= 500",
            name="description_length",
        ),
        Index("idx_agents_slug", "slug"),
        Index(
            "idx_agents_is_retired",
            "is_retired",
            postgresql_where=text("is_retired = false"),
        ),
    )
