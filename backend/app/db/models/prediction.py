from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.match import Match


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    p_home: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    p_draw: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    p_away: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    pred_home_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pred_away_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    match: Mapped[Match] = relationship(Match, lazy="raise")

    __table_args__ = (
        UniqueConstraint("agent_id", "match_id", name="agent_match"),
        CheckConstraint("p_home BETWEEN 0 AND 1", name="p_home_range"),
        CheckConstraint("p_draw BETWEEN 0 AND 1", name="p_draw_range"),
        CheckConstraint("p_away BETWEEN 0 AND 1", name="p_away_range"),
        CheckConstraint(
            "pred_home_goals IS NULL OR pred_home_goals BETWEEN 0 AND 15",
            name="pred_home_goals_range",
        ),
        CheckConstraint(
            "pred_away_goals IS NULL OR pred_away_goals BETWEEN 0 AND 15",
            name="pred_away_goals_range",
        ),
        CheckConstraint(
            "ABS((p_home + p_draw + p_away) - 1.0) < 0.001",
            name="probs_sum_to_one",
        ),
        CheckConstraint(
            "(pred_home_goals IS NULL) = (pred_away_goals IS NULL)",
            name="exact_score_pair",
        ),
        CheckConstraint(
            "reasoning IS NULL OR char_length(reasoning) <= 500",
            name="reasoning_length",
        ),
        Index("idx_predictions_match", "match_id"),
        Index("idx_predictions_agent", "agent_id"),
        Index("idx_predictions_submitted", "submitted_at"),
    )
