"""Osnowa geodezyjna - repery i punkty pomiarowe."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SurveyPoint(db.Model):
    """Punkt osnowy / reper roboczy.

    Wysokosc `h` to rzedna punktu w metrach n.p.m. (uklad wysokosciowy PL-EVRF2007-NH
    albo Kronsztadt'86 - zaleznie od operatu). To ona jest punktem wyjscia dla
    kazdego pomiaru niwelatorem na budowie.
    """

    __tablename__ = "survey_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    nazwa: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # PL-2000 strefa 5: x = polnoc, y = wschod (kolejnosc jak w operacie geodezyjnym)
    x: Mapped[float | None] = mapped_column(Numeric(12, 3))
    y: Mapped[float | None] = mapped_column(Numeric(12, 3))
    h: Mapped[float | None] = mapped_column(Numeric(8, 4))

    uklad: Mapped[str] = mapped_column(String(32), default="PL-2000/5")
    typ: Mapped[str] = mapped_column(String(32), default="OSNOWA")
    opis: Mapped[str | None] = mapped_column(Text)
    aktywny: Mapped[bool] = mapped_column(Boolean, default=True)

    zrodlo: Mapped[str | None] = mapped_column(String(32))
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_survey_point_h", "h"),)

    def __repr__(self) -> str:
        return f"<SurveyPoint {self.nazwa} H={self.h}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nazwa": self.nazwa,
            "x": float(self.x) if self.x is not None else None,
            "y": float(self.y) if self.y is not None else None,
            "h": float(self.h) if self.h is not None else None,
            "uklad": self.uklad,
            "typ": self.typ,
            "aktywny": self.aktywny,
        }
