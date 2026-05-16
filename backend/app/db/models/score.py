from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Score(Base):
    __tablename__ = "scores"

    agent_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    match_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    brier: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    exact_score_pts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    outcome: Mapped[str] = mapped_column(String(1), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("outcome IN ('H','D','A')", name="outcome_enum"),
        Index("idx_scores_match", "match_id"),
    )
