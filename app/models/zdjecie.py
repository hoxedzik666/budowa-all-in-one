"""Zdjecia z budowy.

Po co
-----
Rzedna mowi, ze wykop ma 1,73 m. Zdjecie mowi, ze na dnie stoi woda, podsypka
jest z niewlasciwego kruszywa, a rura lezy na kamieniu. Przy sporze o odbior
to zdjecie jest dowodem, a rzedna tylko liczba.

Gdzie leza pliki
----------------
`data/zdjecia/RRRR-MM/`, czyli **poza `data/exports/`**. Ta roznica jest
istotna: `exports` to cache, ktory wolno skasowac w calosci, bo odtworzy sie
sam. Zdjecia z wykopu nie odtworza sie nigdy - wykop zostanie zasypany.

W bazie trzymamy tylko sciezke i opis. Blob w Postgresie utrudnilby kopie
zapasowa i nie dalby nic w zamian.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Dluzszy bok miniatury. Lista zdjec ma sie wczytywac na telefonie w zasiegu,
# ktory ledwie dziala.
BOK_MINIATURY = 320


class Zdjecie(db.Model):
    """Jedno zdjecie powiazane z tym, czego dotyczy."""

    __tablename__ = "zdjecie"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Cztery mozliwe punkty zaczepienia. Zdjecie zwykle robi sie "przy okazji"
    # pomiaru albo raportu, ale bywa tez samo z siebie - przy obiekcie.
    pomiar_id: Mapped[int | None] = mapped_column(
        ForeignKey("pomiar_wykonawczy.id", ondelete="CASCADE"), index=True)
    raport_id: Mapped[int | None] = mapped_column(
        ForeignKey("raport_dzienny.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("segment.id", ondelete="CASCADE"), index=True)
    obiekt_id: Mapped[int | None] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True)

    # Sciezka wzgledem katalogu zdjec - zeby przeniesienie danych na inny dysk
    # nie wymagalo przepisywania bazy.
    plik: Mapped[str] = mapped_column(String(255), unique=True)
    miniatura: Mapped[str | None] = mapped_column(String(255))

    opis: Mapped[str | None] = mapped_column(Text)
    szerokosc_px: Mapped[int | None] = mapped_column(Integer)
    wysokosc_px: Mapped[int | None] = mapped_column(Integer)
    rozmiar_b: Mapped[int | None] = mapped_column(Integer)

    autor_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL"))
    utworzono: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True)

    autor = relationship("User")
    pomiar = relationship("PomiarWykonawczy")
    raport = relationship("RaportDzienny")
    segment = relationship("Segment")
    obiekt = relationship("NetworkObject")

    __table_args__ = (Index("ix_zdjecie_data_autor", "utworzono", "autor_id"),)

    def __repr__(self) -> str:
        return f"<Zdjecie {self.plik}>"

    @property
    def czego_dotyczy(self) -> str:
        if self.segment is not None:
            return self.segment.nazwa
        if self.obiekt is not None:
            return self.obiekt.kod
        if self.pomiar is not None:
            return self.pomiar.czego_dotyczy
        if self.raport is not None:
            return self.raport.czego_dotyczy
        return "—"

    def sciezka(self, katalog: str | Path) -> Path:
        return Path(katalog) / self.plik

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dotyczy": self.czego_dotyczy,
            "opis": self.opis,
            "szerokosc_px": self.szerokosc_px,
            "wysokosc_px": self.wysokosc_px,
            "rozmiar_kb": round(self.rozmiar_b / 1024) if self.rozmiar_b else None,
            "autor": self.autor.login if self.autor else None,
            "kiedy": self.utworzono.isoformat() if self.utworzono else None,
            "adres": f"/zdjecia/{self.id}.jpg",
            "adres_miniatury": f"/zdjecia/{self.id}-mini.jpg",
        }
