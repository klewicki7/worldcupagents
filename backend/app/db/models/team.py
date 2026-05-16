from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    fifa_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(String, nullable=False)
    name_es: Mapped[str] = mapped_column(String, nullable=False)
    flag_emoji: Mapped[str] = mapped_column(String, nullable=False)
    group_letter: Mapped[str | None] = mapped_column(String(1), nullable=True)
    confederation: Mapped[str | None] = mapped_column(String, nullable=True)
