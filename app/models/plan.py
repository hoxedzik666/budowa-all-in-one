"""Lokalizacje obiektow na planach sytuacyjnych.

Plany sytuacyjne maja wszystkie etykiety zamienione na krzywe wektorowe - w calym
18-stronicowym pliku jest tylko 667 unikalnych slow i ani jednego kodu obiektu.
Pozycje odzyskujemy OCR-em, dlatego kazdy rekord niesie **poziom pewnosci**
i flage recznej weryfikacji. Nic tu nie jest traktowane jak pewnik.

Wspolrzedne trzymamy w punktach PDF danej strony. To wystarcza do wyciecia mapki
i - po przeliczeniu przez skale rysunku - do odleglosci miedzy obiektami.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Skala rysunku 1:1000 -> 1 pt (1/72 cala) = 0.3528 mm na papierze = 0.3528 m w terenie.
MM_NA_PUNKT = 25.4 / 72.0


def punkty_na_metry(odleglosc_pt: float, mianownik_skali: int = 1000) -> float:
    """Zamien odleglosc na rysunku (pkt PDF) na metry w terenie."""
    return round(odleglosc_pt * MM_NA_PUNKT * mianownik_skali / 1000.0, 2)


class PlanSheet(db.Model):
    """Strona planu sytuacyjnego wraz z rozpoznana skala."""

    __tablename__ = "plan_sheet"

    id: Mapped[int] = mapped_column(primary_key=True)
    plik: Mapped[str] = mapped_column(String(255), index=True)
    nr_strony: Mapped[int] = mapped_column(Integer)

    szerokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    wysokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    skala: Mapped[int] = mapped_column(Integer, default=1000)

    # Ile etykiet OCR znalazl i ile z nich dalo sie dopasowac do bazy.
    etykiet_ocr: Mapped[int] = mapped_column(Integer, default=0)
    dopasowanych: Mapped[int] = mapped_column(Integer, default=0)
    uwagi: Mapped[str | None] = mapped_column(Text)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lokalizacje = relationship("PlanLocation", back_populates="strona",
                               cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PlanSheet s.{self.nr_strony} 1:{self.skala}>"


class PlanLocation(db.Model):
    """Gdzie na planie lezy dany obiekt - wynik OCR albo recznego wskazania."""

    __tablename__ = "plan_location"

    id: Mapped[int] = mapped_column(primary_key=True)
    obiekt_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )
    strona_id: Mapped[int] = mapped_column(
        ForeignKey("plan_sheet.id", ondelete="CASCADE"), index=True
    )

    x_pt: Mapped[float] = mapped_column(Numeric(10, 2))
    y_pt: Mapped[float] = mapped_column(Numeric(10, 2))

    # 0-100 wg tesseracta. Ponizej PROG_PEWNOSCI oznaczamy jako niepewne.
    pewnosc: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tekst_ocr: Mapped[str | None] = mapped_column(String(64))
    zrodlo: Mapped[str] = mapped_column(String(16), default="OCR")
    zweryfikowane: Mapped[bool] = mapped_column(Boolean, default=False)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    obiekt = relationship("NetworkObject")
    strona = relationship("PlanSheet", back_populates="lokalizacje")

    __table_args__ = (Index("ix_plan_location_obiekt_strona", "obiekt_id", "strona_id"),)

    def __repr__(self) -> str:
        return f"<PlanLocation {self.obiekt.kod if self.obiekt else '?'} s.{self.strona_id}>"

    @property
    def pewna(self) -> bool:
        return bool(self.zweryfikowane) or (self.pewnosc is not None and float(self.pewnosc) >= 70)

    def to_dict(self) -> dict:
        return {
            "obiekt": self.obiekt.kod if self.obiekt else None,
            "nr_strony": self.strona.nr_strony if self.strona else None,
            "x_pt": float(self.x_pt),
            "y_pt": float(self.y_pt),
            "pewnosc": float(self.pewnosc) if self.pewnosc is not None else None,
            "pewna": self.pewna,
            "tekst_ocr": self.tekst_ocr,
            "zrodlo": self.zrodlo,
            "zweryfikowane": self.zweryfikowane,
        }
