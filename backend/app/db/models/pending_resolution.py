from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingResolution(Base):
    __tablename__ = "pending_resolutions"

    match_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    suggested_home: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    suggested_away: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    went_to_penalties: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    penalties_home: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    penalties_away: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_pending_resolutions_fetched", "fetched_at"),)
