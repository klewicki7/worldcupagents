from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
    )
    p_home: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    p_draw: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    p_away: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    pred_home_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pred_away_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    snapshotted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_prediction_history_pred",
            "prediction_id",
            "snapshotted_at",
        ),
    )
