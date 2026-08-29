"""Zadania - globalne albo przypisane do konkretnego konta.

Zadanie moze wskazywac na obiekt albo odcinek sieci, dzieki czemu z karty
odcinka widac, co jest na nim do zrobienia ("D155 - wyregulowac wlaz",
"Wyl101-D155 - proba szczelnosci").

`przypisany_do_id IS NULL` oznacza **zadanie globalne** - widzi je kazdy.
"""
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class StatusZadania(str, enum.Enum):
    NOWE = "NOWE"
    W_TRAKCIE = "W_TRAKCIE"
    ZROBIONE = "ZROBIONE"
    ANULOWANE = "ANULOWANE"


class Priorytet(str, enum.Enum):
    NISKI = "NISKI"
    ZWYKLY = "ZWYKLY"
    WYSOKI = "WYSOKI"
    PILNY = "PILNY"


# Statusy, ktore liczymy jako "otwarte" - do licznika w nawigacji.
OTWARTE = (StatusZadania.NOWE, StatusZadania.W_TRAKCIE)


class Task(db.Model):
    __tablename__ = "zadanie"

    id: Mapped[int] = mapped_column(primary_key=True)
    tytul: Mapped[str] = mapped_column(String(200))
    opis: Mapped[str | None] = mapped_column(Text)

    status: Mapped[StatusZadania] = mapped_column(
        Enum(StatusZadania, name="status_zadania"), default=StatusZadania.NOWE, index=True
    )
    priorytet: Mapped[Priorytet] = mapped_column(
        Enum(Priorytet, name="priorytet"), default=Priorytet.ZWYKLY
    )
    termin: Mapped[date | None] = mapped_column(Date)

    autor_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL"), index=True
    )
    # NULL = zadanie globalne, widoczne dla wszystkich
    przypisany_do_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL"), index=True
    )

    # Opcjonalne powiazanie z siecia
    obiekt_id: Mapped[int | None] = mapped_column(
        ForeignKey("network_object.id", ondelete="SET NULL"), index=True
    )
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("segment.id", ondelete="SET NULL"), index=True
    )

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    zakonczono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    autor = relationship("User", foreign_keys=[autor_id], back_populates="zadania_utworzone")
    przypisany_do = relationship(
        "User", foreign_keys=[przypisany_do_id], back_populates="zadania_przypisane"
    )
    obiekt = relationship("NetworkObject")
    segment = relationship("Segment")

    __table_args__ = (Index("ix_zadanie_status_przypisany", "status", "przypisany_do_id"),)

    def __repr__(self) -> str:
        return f"<Task {self.id} {self.tytul[:30]}>"

    @property
    def globalne(self) -> bool:
        return self.przypisany_do_id is None

    @property
    def otwarte(self) -> bool:
        return self.status in OTWARTE

    @property
    def po_terminie(self) -> bool:
        return bool(self.termin and self.otwarte and self.termin < date.today())

    @property
    def czego_dotyczy(self) -> str | None:
        if self.segment is not None:
            return self.segment.nazwa
        if self.obiekt is not None:
            return self.obiekt.kod
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tytul": self.tytul,
            "opis": self.opis,
            "status": self.status.value if self.status else None,
            "priorytet": self.priorytet.value if self.priorytet else None,
            "termin": self.termin.isoformat() if self.termin else None,
            "globalne": self.globalne,
            "po_terminie": self.po_terminie,
            "autor": self.autor.login if self.autor else None,
            "przypisany_do": self.przypisany_do.login if self.przypisany_do else None,
            "czego_dotyczy": self.czego_dotyczy,
            "utworzono": self.utworzono.isoformat() if self.utworzono else None,
        }
