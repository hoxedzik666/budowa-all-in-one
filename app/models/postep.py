"""Postep robot: stan odcinka i raporty dzienne brygady.

Dwa zapisy tej samej roboty, celowo rozdzielone
---------------------------------------------
`Segment.status` mowi, **w jakim stanie jest odcinek teraz**. Raport dzienny
mowi, **co brygada zrobila danego dnia**. To nie jest to samo i nie da sie
jednego wyliczyc z drugiego: odcinek bywa ulozony przez trzy dni, a jednego dnia
brygada dotyka czterech odcinkow.

Historia zamiast nadpisywania
-----------------------------
Przy odbiorze pada pytanie "kto i kiedy". Samo pole `status` na to nie odpowie,
bo pamieta tylko ostatnia wartosc. Dlatego kazda zmiana zostawia wpis
w `zmiana_statusu` - tak samo jak pomiar wykonawczy nie nadpisuje projektu,
tylko sie do niego dokleja.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
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
from app.models.enums import StatusWykonania

# Kolejnosc stanow na budowie. Indeks w tej krotce mowi, czy ruch jest do przodu.
SCIEZKA = (
    StatusWykonania.PROJEKT,
    StatusWykonania.WYTYCZONY,
    StatusWykonania.W_TRAKCIE,
    StatusWykonania.WYKONANY,
    StatusWykonania.ODEBRANY,
)

# Stany, ktore moze ustawic wylacznie kierownictwo. Zglosic wykonanie moze
# kazdy, kto stoi w wykopie - ale odbior jest decyzja kierownika.
STANY_KIEROWNICTWA = (StatusWykonania.ODEBRANY,)

# Odcinek uznany za zrobiony - do liczenia procentu wykonania sieci.
STANY_GOTOWE = (StatusWykonania.WYKONANY, StatusWykonania.ODEBRANY)

ETYKIETY = {
    StatusWykonania.PROJEKT: "w projekcie",
    StatusWykonania.WYTYCZONY: "wytyczony",
    StatusWykonania.W_TRAKCIE: "w trakcie",
    StatusWykonania.WYKONANY: "wykonany",
    StatusWykonania.ODEBRANY: "odebrany",
}

# Kolory warstwy postepu na mapie i plakietek w tabelach.
KOLORY = {
    StatusWykonania.PROJEKT: "#adb5bd",
    StatusWykonania.WYTYCZONY: "#ffc107",
    StatusWykonania.W_TRAKCIE: "#fd7e14",
    StatusWykonania.WYKONANY: "#0d6efd",
    StatusWykonania.ODEBRANY: "#198754",
}

KLASY_PLAKIETKI = {
    StatusWykonania.PROJEKT: "text-bg-secondary",
    StatusWykonania.WYTYCZONY: "text-bg-warning",
    StatusWykonania.W_TRAKCIE: "text-bg-warning",
    StatusWykonania.WYKONANY: "text-bg-primary",
    StatusWykonania.ODEBRANY: "text-bg-success",
}


def nastepny_stan(obecny: StatusWykonania) -> StatusWykonania | None:
    """Kolejny krok naprzod albo None, gdy odcinek jest juz odebrany."""
    pozycja = SCIEZKA.index(obecny)
    return SCIEZKA[pozycja + 1] if pozycja + 1 < len(SCIEZKA) else None


def poprzedni_stan(obecny: StatusWykonania) -> StatusWykonania | None:
    pozycja = SCIEZKA.index(obecny)
    return SCIEZKA[pozycja - 1] if pozycja > 0 else None


def wolno_ustawic(uzytkownik, obecny: StatusWykonania,
                  nowy: StatusWykonania) -> tuple[bool, str]:
    """Czy ta osoba moze przestawic odcinek w ten stan.

    Zwraca (wolno, powod odmowy). Reguly sa dwie i obie dotycza odbioru:
    odebrac moze tylko kierownictwo i tylko ono moze odbior cofnac.
    """
    if nowy is obecny:
        return False, "Odcinek już jest w tym stanie."

    if nowy in STANY_KIEROWNICTWA and not uzytkownik.moze_odbierac:
        return False, ("Odbiór odcinka należy do kierownika budowy. "
                       "Zgłoś wykonanie — kierownik odbierze.")

    if obecny in STANY_KIEROWNICTWA and not uzytkownik.moze_odbierac:
        return False, "Cofnąć odbiór może tylko kierownik budowy."

    return True, ""


class ZmianaStatusu(db.Model):
    """Jeden ruch odcinka na sciezce robot - z podpisem i data."""

    __tablename__ = "zmiana_statusu"

    id: Mapped[int] = mapped_column(primary_key=True)
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segment.id", ondelete="CASCADE"), index=True
    )

    poprzedni: Mapped[StatusWykonania | None] = mapped_column(
        Enum(StatusWykonania, name="status_wykonania")
    )
    nowy: Mapped[StatusWykonania] = mapped_column(
        Enum(StatusWykonania, name="status_wykonania")
    )

    autor_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL")
    )
    uwagi: Mapped[str | None] = mapped_column(Text)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    segment = relationship("Segment")
    autor = relationship("User")

    __table_args__ = (Index("ix_zmiana_statusu_segment_data", "segment_id", "utworzono"),)

    def to_dict(self) -> dict:
        return {
            "poprzedni": self.poprzedni.value if self.poprzedni else None,
            "nowy": self.nowy.value,
            "etykieta": ETYKIETY.get(self.nowy, self.nowy.value),
            "autor": self.autor.login if self.autor else None,
            "uwagi": self.uwagi,
            "kiedy": self.utworzono.isoformat() if self.utworzono else None,
        }


class RaportDzienny(db.Model):
    """Co brygada zrobila danego dnia.

    Pola ida za papierowym raportem dziennym, bo taki i tak powstaje na budowie.
    Przestoj ma wlasna rubryke nie dla statystyki: udokumentowany przestoj bywa
    podstawa roszczenia terminowego, a przypomniany po miesiacu jest bezwartosciowy.
    """

    __tablename__ = "raport_dzienny"

    id: Mapped[int] = mapped_column(primary_key=True)

    data_raportu: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    autor_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL"), index=True
    )
    brygada: Mapped[str | None] = mapped_column(String(64))

    # Odcinek, ktorego raport dotyczy. Puste = praca nieprzypisana do odcinka
    # (np. dowoz materialu, przygotowanie zaplecza).
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("segment.id", ondelete="SET NULL"), index=True
    )
    obiekt_id: Mapped[int | None] = mapped_column(
        ForeignKey("network_object.id", ondelete="SET NULL")
    )

    opis: Mapped[str] = mapped_column(Text)
    metry: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ludzi: Mapped[int | None] = mapped_column(Integer)
    sprzet: Mapped[str | None] = mapped_column(String(255))
    pogoda: Mapped[str | None] = mapped_column(String(128))

    przestoj_godziny: Mapped[float | None] = mapped_column(Numeric(5, 2))
    przestoj_powod: Mapped[str | None] = mapped_column(String(255))

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    autor = relationship("User")
    segment = relationship("Segment")
    obiekt = relationship("NetworkObject")

    __table_args__ = (Index("ix_raport_data_autor", "data_raportu", "autor_id"),)

    def __repr__(self) -> str:
        return f"<Raport {self.data_raportu} {self.czego_dotyczy}>"

    @property
    def czego_dotyczy(self) -> str:
        if self.segment is not None:
            return self.segment.nazwa
        if self.obiekt is not None:
            return self.obiekt.kod
        return "—"

    @property
    def byl_przestoj(self) -> bool:
        return bool(self.przestoj_godziny and float(self.przestoj_godziny) > 0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "data": self.data_raportu.isoformat() if self.data_raportu else None,
            "autor": self.autor.login if self.autor else None,
            "brygada": self.brygada,
            "dotyczy": self.czego_dotyczy,
            "opis": self.opis,
            "metry": float(self.metry) if self.metry is not None else None,
            "ludzi": self.ludzi,
            "sprzet": self.sprzet,
            "pogoda": self.pogoda,
            "przestoj_godziny": (
                float(self.przestoj_godziny) if self.przestoj_godziny is not None else None),
            "przestoj_powod": self.przestoj_powod,
        }
