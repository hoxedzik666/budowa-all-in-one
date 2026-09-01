"""Audyt importow - zeby zawsze bylo wiadomo skad wzieta jest kazda liczba."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.typy import JSON_ELASTYCZNY


class ImportRun(db.Model):
    """Jeden przebieg importu pliku zrodlowego."""

    __tablename__ = "import_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    plik: Mapped[str] = mapped_column(String(255), index=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    typ_importu: Mapped[str] = mapped_column(String(32))

    liczba_profili: Mapped[int] = mapped_column(Integer, default=0)
    liczba_obiektow: Mapped[int] = mapped_column(Integer, default=0)
    liczba_odcinkow: Mapped[int] = mapped_column(Integer, default=0)
    liczba_ostrzezen: Mapped[int] = mapped_column(Integer, default=0)

    # Lista rozbieznosci: niezmiennik zaglebienia, spadek vs rzedne, PDF vs XLSX.
    ostrzezenia: Mapped[list | None] = mapped_column(JSON_ELASTYCZNY)
    statystyki: Mapped[dict | None] = mapped_column(JSON_ELASTYCZNY)
    blad: Mapped[str | None] = mapped_column(Text)

    rozpoczeto: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zakonczono: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<ImportRun {self.typ_importu} {self.plik}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plik": self.plik,
            "typ_importu": self.typ_importu,
            "liczba_profili": self.liczba_profili,
            "liczba_obiektow": self.liczba_obiektow,
            "liczba_odcinkow": self.liczba_odcinkow,
            "liczba_ostrzezen": self.liczba_ostrzezen,
            "statystyki": self.statystyki,
            "rozpoczeto": self.rozpoczeto.isoformat() if self.rozpoczeto else None,
            "zakonczono": self.zakonczono.isoformat() if self.zakonczono else None,
        }
