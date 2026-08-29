"""Dziennik wykonawczy - co naprawde wyszlo w wykopie.

Po co osobna tabela
-------------------
Cala dotychczasowa baza opisuje **projekt**: co ma byc zbudowane i na jakiej
rzednej. Budowa to jednak nie jest przepisywanie projektu - rura laduje o dwa
centymetry wyzej, teren okazuje sie nizszy, a studnia wchodzi na innej rzednej
niz rysunek przewiduje. Te liczby trzeba gdzies zapisac, i **nie wolno ich
mieszac z projektem**: gdyby pomiar nadpisywal `network_object.rzedna_dna_kanalu`,
po tygodniu nikt nie wiedzialby, co bylo zaprojektowane, a co wykonane.

Dlatego pomiar jest osobnym rekordem, ktory tylko **wskazuje** na obiekt albo
odcinek. Projekt zostaje nietkniety, a odchylke program liczy w locie.

Skad sie biora te liczby
------------------------
Wprost z niwelatora: brygadzista odczytuje late, wpisuje rzedna, a program
od razu pokazuje, o ile odbiega od projektu i czy miesci sie w tolerancji.
To te same rzedne, ktore chwile wczesniej wylicza kalkulator ciagu rur.
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Ile moze odbiegac wykonanie od projektu, zanim to jest problem.
# Dla kanalizacji grawitacyjnej rzedna dna jest krytyczna - blad 3 cm na
# krotkim odcinku potrafi odwrocic spadek. Teren jest znacznie mniej wrazliwy.
TOLERANCJE_M = {
    "DNO_KANALU": 0.02,
    "DNO_STUDNI": 0.03,
    "TEREN": 0.05,
    "INNE": 0.05,
}


class RodzajPomiaru(str, enum.Enum):
    DNO_KANALU = "DNO_KANALU"      # ciek rury - najwazniejsza liczba na budowie
    DNO_STUDNI = "DNO_STUDNI"
    TEREN = "TEREN"
    INNE = "INNE"


class PomiarWykonawczy(db.Model):
    """Jeden odczyt z niwelatora zapisany po wykonaniu roboty."""

    __tablename__ = "pomiar_wykonawczy"

    id: Mapped[int] = mapped_column(primary_key=True)

    obiekt_id: Mapped[int | None] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("segment.id", ondelete="CASCADE"), index=True
    )

    rodzaj: Mapped[RodzajPomiaru] = mapped_column(
        Enum(RodzajPomiaru, name="rodzaj_pomiaru"), default=RodzajPomiaru.DNO_KANALU
    )
    rzedna_zmierzona: Mapped[float] = mapped_column(Numeric(8, 3))
    # Gdzie wzdluz odcinka - puste znaczy "przy obiekcie".
    odleglosc_m: Mapped[float | None] = mapped_column(Numeric(10, 2))

    data_pomiaru: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    autor_id: Mapped[int | None] = mapped_column(
        ForeignKey("uzytkownik.id", ondelete="SET NULL")
    )
    uwagi: Mapped[str | None] = mapped_column(Text)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    obiekt = relationship("NetworkObject")
    segment = relationship("Segment")
    autor = relationship("User")

    __table_args__ = (
        Index("ix_pomiar_data_obiekt", "data_pomiaru", "obiekt_id"),
    )

    def __repr__(self) -> str:
        return f"<Pomiar {self.czego_dotyczy} {self.rzedna_zmierzona}>"

    # ---------------------------------------------------------- wyliczenia

    @property
    def czego_dotyczy(self) -> str:
        if self.segment is not None:
            return self.segment.nazwa
        if self.obiekt is not None:
            return self.obiekt.kod
        return "—"

    @property
    def rzedna_projektowa(self) -> float | None:
        """Wartosc z dokumentacji, do ktorej porownujemy pomiar.

        Na odcinku rzedna zalezy od miejsca: liczymy ja ze spadku, tak samo
        jak robi to kalkulator tyczenia.
        """
        if self.segment is not None and self.odleglosc_m is not None:
            return self._rzedna_na_odcinku()
        if self.obiekt is None:
            return None
        if self.rodzaj == RodzajPomiaru.TEREN:
            wartosc = self.obiekt.rzedna_terenu_proj
        elif self.rodzaj == RodzajPomiaru.DNO_STUDNI:
            wartosc = self.obiekt.rzedna_dna_studni or self.obiekt.rzedna_dna_kanalu
        else:
            wartosc = self.obiekt.rzedna_dna_kanalu
        return float(wartosc) if wartosc is not None else None

    def _rzedna_na_odcinku(self) -> float | None:
        """Rzedna projektowa w danym miejscu odcinka.

        Odleglosc liczy sie **od obiektu, ktory jest pierwszy w nazwie**:
        na odcinku Wyl101-D155 metr zerowy jest przy Wyl101. Interpolujemy
        wiec wprost od `rzedna_dna_od` do `rzedna_dna_do`, bez zgadywania,
        ktory koniec jest wyzszy - profile bywaja rysowane w obie strony
        (patrz `Segment.kierunek_rysunku`) i takie zgadywanie odwracalo
        wynik na wiekszosci odcinkow.
        """
        odc = self.segment
        if odc.rzedna_dna_od is None or odc.rzedna_dna_do is None or not odc.dlugosc_m:
            return None
        poczatek = float(odc.rzedna_dna_od)
        koniec = float(odc.rzedna_dna_do)
        udzial = min(max(float(self.odleglosc_m) / float(odc.dlugosc_m), 0.0), 1.0)
        return round(poczatek + (koniec - poczatek) * udzial, 3)

    @property
    def odchylka_m(self) -> float | None:
        """Wykonanie minus projekt. Dodatnia znaczy: wyzej niz mialo byc."""
        projekt = self.rzedna_projektowa
        if projekt is None:
            return None
        return round(float(self.rzedna_zmierzona) - projekt, 3)

    @property
    def tolerancja_m(self) -> float:
        return TOLERANCJE_M.get(self.rodzaj.value, 0.05)

    @property
    def w_tolerancji(self) -> bool | None:
        odchylka = self.odchylka_m
        if odchylka is None:
            return None
        return abs(odchylka) <= self.tolerancja_m

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dotyczy": self.czego_dotyczy,
            "rodzaj": self.rodzaj.value,
            "rzedna_zmierzona": float(self.rzedna_zmierzona),
            "rzedna_projektowa": self.rzedna_projektowa,
            "odchylka_m": self.odchylka_m,
            "tolerancja_m": self.tolerancja_m,
            "w_tolerancji": self.w_tolerancji,
            "odleglosc_m": float(self.odleglosc_m) if self.odleglosc_m is not None else None,
            "data_pomiaru": self.data_pomiaru.isoformat() if self.data_pomiaru else None,
            "autor": self.autor.login if self.autor else None,
            "uwagi": self.uwagi,
        }


def spadek_wykonany(pomiary: list["PomiarWykonawczy"], segment=None) -> dict | None:
    """Rzeczywisty spadek policzony z dwoch skrajnych pomiarow na odcinku.

    To jest liczba, ktorej szuka kierownik przy odbiorze: nie "czy rzedne sie
    zgadzaja", tylko **czy woda poplynie**. Rura ulozona o 2 cm za wysoko na
    obu koncach ma nadal poprawny spadek; ulozona o 2 cm za wysoko tylko
    na koncu - juz nie.

    Znak jest liczony wzdluz rosnacej odleglosci, czyli w kierunku od `obiekt_od`
    do `obiekt_do`. Czy to jest kierunek splywu, zalezy od tego, jak narysowano
    profil - dlatego porownujemy go z kierunkiem projektowym tego samego
    odcinka, a nie z zalozeniem "w dol znaczy dodatni".
    """
    z_odlegloscia = [p for p in pomiary if p.odleglosc_m is not None
                     and p.rodzaj == RodzajPomiaru.DNO_KANALU]
    if len(z_odlegloscia) < 2:
        return None

    z_odlegloscia.sort(key=lambda p: float(p.odleglosc_m))
    pierwszy, ostatni = z_odlegloscia[0], z_odlegloscia[-1]
    dlugosc = float(ostatni.odleglosc_m) - float(pierwszy.odleglosc_m)
    if dlugosc <= 0:
        return None

    roznica = float(pierwszy.rzedna_zmierzona) - float(ostatni.rzedna_zmierzona)
    wynik = {
        "dlugosc_m": round(dlugosc, 2),
        "roznica_m": round(roznica, 3),
        "spadek_promile": round(abs(roznica) / dlugosc * 1000, 2),
        "punktow": len(z_odlegloscia),
        "poprawny_kierunek": None,
        "roznica_do_projektu_promile": None,
    }

    if segment is not None and segment.rzedna_dna_od is not None             and segment.rzedna_dna_do is not None:
        projektowa_roznica = float(segment.rzedna_dna_od) - float(segment.rzedna_dna_do)
        # Woda ma plynac w te sama strone, co w projekcie. Zero po ktorejkolwiek
        # stronie oznacza odcinek plaski - wtedy o kierunku nie ma co mowic.
        wynik["poprawny_kierunek"] = (roznica * projektowa_roznica) > 0
        if segment.spadek_promile is not None:
            wynik["roznica_do_projektu_promile"] = round(
                wynik["spadek_promile"] - abs(float(segment.spadek_promile)), 2)

    return wynik
