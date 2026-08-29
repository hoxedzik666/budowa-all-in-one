"""Gospodarka materialowa - arkusz RURY z pliku Material.xlsx."""
import re
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db

# Opis pozycji koduje srednice i dlugosc sztuki:
#   "PP Rura kanal. SN 8 500/3 CZ/SZ OD PRAGMA"  ->  OD500, sztuka 3 m, SN8
# Kolumna DLUGOSC w arkuszu bywa pusta, wiec czytamy wprost z nazwy pozycji.
RE_DN_DLUGOSC = re.compile(r"(\d{3,4})\s*/\s*(\d{1,2})\b")
RE_SN = re.compile(r"\bSN\s*(\d{1,2})\b", re.I)

# Druga liczba w "500/3" to dlugosc handlowa (3 albo 6 m), nie kolejna srednica.
# Bez tego ograniczenia "Trojnik redukcyjny OD 200/200/160" wygladalby jak rura 200 m.
MAX_DLUGOSC_SZTUKI_M = 12.0


def rozbierz_opis(opis: str) -> dict:
    """Wyciagnij z nazwy pozycji srednice zewnetrzna, dlugosc sztuki i klase SN."""
    dane = {"dn_od_mm": None, "dlugosc_sztuki_m": None, "klasa_sn": None}
    if not opis:
        return dane
    if "rura" in opis.lower() and (m := RE_DN_DLUGOSC.search(opis)):
        dlugosc = float(m.group(2))
        if 0 < dlugosc <= MAX_DLUGOSC_SZTUKI_M:
            dane["dn_od_mm"] = int(m.group(1))
            dane["dlugosc_sztuki_m"] = dlugosc
    if (m := RE_SN.search(opis)):
        dane["klasa_sn"] = f"SN{m.group(1)}"
    return dane


class MaterialItem(db.Model):
    """Pozycja materialowa: ile zaprojektowano, ile dojechalo, na jakim WZ."""

    __tablename__ = "material_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    opis_pozycji: Mapped[str] = mapped_column(String(255), index=True)

    # Rozpoznane z opisu - po tym laczymy pozycje katalogowa z odcinkiem.
    dn_od_mm: Mapped[int | None] = mapped_column(Integer, index=True)
    dlugosc_sztuki_m: Mapped[float | None] = mapped_column(Numeric(8, 2))
    klasa_sn: Mapped[str | None] = mapped_column(String(8))

    ilosc_projekt_m: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ilosc_zamowiona_m: Mapped[float | None] = mapped_column(Numeric(12, 2))
    ilosc_dostarczona_m: Mapped[float | None] = mapped_column(Numeric(12, 2))

    data_dostawy: Mapped[str | None] = mapped_column(String(128))
    nr_wz: Mapped[str | None] = mapped_column(String(128))
    uwagi: Mapped[str | None] = mapped_column(Text)

    arkusz: Mapped[str | None] = mapped_column(String(64))
    wiersz_zrodlowy: Mapped[int | None] = mapped_column(Integer)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_material_dn_dlugosc", "dn_od_mm", "dlugosc_sztuki_m"),)

    def __repr__(self) -> str:
        return f"<Material {self.opis_pozycji[:40]}>"

    @property
    def brakuje_m(self) -> float | None:
        if self.ilosc_projekt_m is None:
            return None
        dostarczono = float(self.ilosc_dostarczona_m or 0)
        return round(float(self.ilosc_projekt_m) - dostarczono, 2)

    @property
    def sztuk_dostarczonych(self) -> int | None:
        if not self.ilosc_dostarczona_m or not self.dlugosc_sztuki_m:
            return None
        return int(float(self.ilosc_dostarczona_m) / float(self.dlugosc_sztuki_m))

    def to_dict(self) -> dict:
        f = lambda v: float(v) if v is not None else None  # noqa: E731
        return {
            "id": self.id,
            "opis_pozycji": self.opis_pozycji,
            "dn_od_mm": self.dn_od_mm,
            "dlugosc_sztuki_m": f(self.dlugosc_sztuki_m),
            "klasa_sn": self.klasa_sn,
            "ilosc_projekt_m": f(self.ilosc_projekt_m),
            "ilosc_zamowiona_m": f(self.ilosc_zamowiona_m),
            "ilosc_dostarczona_m": f(self.ilosc_dostarczona_m),
            "sztuk_dostarczonych": self.sztuk_dostarczonych,
            "brakuje_m": self.brakuje_m,
            "data_dostawy": self.data_dostawy,
            "nr_wz": self.nr_wz,
        }
