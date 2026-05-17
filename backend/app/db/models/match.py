from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.team import Team


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    group_letter: Mapped[str | None] = mapped_column(String(1), nullable=True)
    home_team_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("teams.id"), nullable=True
    )
    away_team_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("teams.id"), nullable=True
    )
    home_placeholder: Mapped[str | None] = mapped_column(String, nullable=True)
    away_placeholder: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String, nullable=True)
    venue_country: Mapped[str | None] = mapped_column(String, nullable=True)
    kickoff_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lock_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'scheduled'")
    )
    home_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    went_to_penalties: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    penalties_home: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    penalties_away: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    home_team: Mapped[Team | None] = relationship(Team, foreign_keys=[home_team_id], lazy="raise")
    away_team: Mapped[Team | None] = relationship(Team, foreign_keys=[away_team_id], lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "stage IN ('group','r32','r16','qf','sf','third','final')",
            name="stage_enum",
        ),
        CheckConstraint(
            "status IN ('scheduled','live','finished','cancelled')",
            name="status_enum",
        ),
        CheckConstraint(
            "status != 'finished' OR (home_goals IS NOT NULL AND away_goals IS NOT NULL)",
            name="score_when_finished",
        ),
        CheckConstraint(
            "NOT went_to_penalties OR (penalties_home IS NOT NULL AND penalties_away IS NOT NULL)",
            name="penalties_consistency",
        ),
        Index("idx_matches_kickoff", "kickoff_at"),
        Index("idx_matches_status", "status"),
        Index("idx_matches_stage", "stage"),
        Index("idx_matches_lock_at", "lock_at"),
    )
