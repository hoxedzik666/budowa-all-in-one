"""Obliczenia niwelacyjne - to, co brygadzista robi z niwelatorem przy wykopie.

Cala matematyka niwelacji geometrycznej "ze srodka" sprowadza sie do jednej
wielkosci posredniej: HI (wysokosc celowej / horyzont instrumentu).

    HI = H_repera + odczyt_wstecz        (lata stoi na reperze o znanej rzednej)
    H_punktu = HI - odczyt_wprzod        (lata stoi na mierzonym punkcie)

Z tego wynika najwazniejszy wzor roboczy - ile MA pokazac lata, zeby dno
kanalu wyszlo na rzednej projektowej:

    odczyt_zadany = HI - rzedna_projektowa

Jesli lata pokazuje wiecej niz odczyt zadany - jest za nisko (przekopane).
Jesli mniej - za wysoko (trzeba dobrac).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Stanowisko:
    """Jedno ustawienie niwelatora."""

    reper: str
    rzedna_repera: float
    odczyt_wstecz: float

    @property
    def hi(self) -> float:
        """Wysokosc celowej (horyzont instrumentu) w m n.p.m."""
        return round(self.rzedna_repera + self.odczyt_wstecz, 4)

    def rzedna_punktu(self, odczyt_wprzod: float) -> float:
        return round(self.hi - odczyt_wprzod, 4)

    def odczyt_zadany(self, rzedna_projektowa: float) -> float:
        """Ile ma pokazac lata, zeby punkt lezal na rzednej projektowej."""
        return round(self.hi - rzedna_projektowa, 4)


# Typowa lata niwelacyjna ma 4 m. Odczyt spoza zakresu 0..DLUGOSC_LATY_M
# oznacza, ze z tego stanowiska punktu po prostu nie da sie wytyczyc.
DLUGOSC_LATY_M = 4.0


@dataclass
class WynikTyczenia:
    hi: float
    rzedna_projektowa: float
    odczyt_zadany: float
    odczyt_zmierzony: float | None = None
    roznica: float | None = None
    ocena: str | None = None
    wykonalne: bool = True
    uwaga: str | None = None

    def to_dict(self) -> dict:
        return {
            "hi": self.hi,
            "rzedna_projektowa": self.rzedna_projektowa,
            "odczyt_zadany": self.odczyt_zadany,
            "odczyt_zmierzony": self.odczyt_zmierzony,
            "roznica": self.roznica,
            "ocena": self.ocena,
            "wykonalne": self.wykonalne,
            "uwaga": self.uwaga,
        }


def wytycz(
    rzedna_repera: float,
    odczyt_wstecz: float,
    rzedna_projektowa: float,
    odczyt_zmierzony: float | None = None,
    tolerancja_m: float = 0.01,
    reper: str = "reper",
) -> WynikTyczenia:
    """Podstawowa operacja przy ukladaniu rury na zadanej rzednej."""
    st = Stanowisko(reper=reper, rzedna_repera=rzedna_repera, odczyt_wstecz=odczyt_wstecz)
    zadany = st.odczyt_zadany(rzedna_projektowa)

    wynik = WynikTyczenia(hi=st.hi, rzedna_projektowa=rzedna_projektowa, odczyt_zadany=zadany)

    # Kontrola wykonalnosci - zanim ktokolwiek pojdzie z lata do wykopu.
    if zadany < 0:
        wynik.wykonalne = False
        wynik.uwaga = (
            f"Celowa jest {abs(zadany):.3f} m PONIZEJ rzednej projektowej. "
            "Z tego stanowiska punktu nie zobaczysz - przenies niwelator wyzej "
            "albo nawiaz sie na wyzszy reper."
        )
    elif zadany > DLUGOSC_LATY_M:
        wynik.wykonalne = False
        wynik.uwaga = (
            f"Odczyt zadany {zadany:.3f} m przekracza dlugosc laty ({DLUGOSC_LATY_M:.1f} m). "
            "Potrzebne stanowisko posrednie."
        )

    if odczyt_zmierzony is not None:
        # Odczyt wiekszy od zadanego => lata nizej => punkt ponizej projektu (przekop).
        roznica = round(zadany - odczyt_zmierzony, 4)
        wynik.odczyt_zmierzony = odczyt_zmierzony
        wynik.roznica = roznica
        if abs(roznica) <= tolerancja_m:
            wynik.ocena = "OK"
        elif roznica < 0:
            wynik.ocena = f"ZA NISKO o {abs(roznica):.3f} m - dosypac/podniesc"
        else:
            wynik.ocena = f"ZA WYSOKO o {roznica:.3f} m - dobrac gruntu"
    return wynik


def rzedna_posrednia(
    rzedna_poczatkowa: float, spadek_promile: float, odleglosc_m: float
) -> float:
    """Rzedna dna w dowolnym miejscu odcinka.

    Spadek dodatni = kanal opada zgodnie z kierunkiem przeplywu.
    """
    return round(rzedna_poczatkowa - spadek_promile / 1000.0 * odleglosc_m, 4)


def spadek_z_rzednych(rzedna_od: float, rzedna_do: float, dlugosc_m: float) -> float | None:
    """Spadek w promilach policzony z dwoch rzednych i dlugosci."""
    if not dlugosc_m:
        return None
    return round((rzedna_od - rzedna_do) / dlugosc_m * 1000.0, 3)


@dataclass
class CiagNiwelacyjny:
    """Ciag zamkniety/nawiazany - kontrola poprawnosci pomiaru.

    Odchylka dopuszczalna wg instrukcji technicznej dla niwelacji technicznej:
        f_dop = 20 mm * sqrt(L_km)      (teren zabudowany / budowa)
    """

    stanowiska: list[tuple[float, float]] = field(default_factory=list)  # (wstecz, wprzod)
    rzedna_poczatkowa: float = 0.0
    rzedna_koncowa_dana: float | None = None
    dlugosc_km: float = 0.0

    def przewyzszenie(self) -> float:
        return round(sum(w - p for w, p in self.stanowiska), 4)

    def rzedna_koncowa_obliczona(self) -> float:
        return round(self.rzedna_poczatkowa + self.przewyzszenie(), 4)

    def odchylka(self) -> float | None:
        if self.rzedna_koncowa_dana is None:
            return None
        return round(self.rzedna_koncowa_obliczona() - self.rzedna_koncowa_dana, 4)

    def odchylka_dopuszczalna_m(self) -> float:
        return round(0.020 * math.sqrt(max(self.dlugosc_km, 0.0001)), 4)

    def czy_ok(self) -> bool | None:
        odch = self.odchylka()
        if odch is None:
            return None
        return abs(odch) <= self.odchylka_dopuszczalna_m()

    def to_dict(self) -> dict:
        return {
            "przewyzszenie": self.przewyzszenie(),
            "rzedna_koncowa_obliczona": self.rzedna_koncowa_obliczona(),
            "rzedna_koncowa_dana": self.rzedna_koncowa_dana,
            "odchylka": self.odchylka(),
            "odchylka_dopuszczalna": self.odchylka_dopuszczalna_m(),
            "czy_ok": self.czy_ok(),
            "liczba_stanowisk": len(self.stanowiska),
        }


def przykrycie(rzedna_terenu: float, rzedna_dna: float, dn_mm: int | None) -> float | None:
    """Przykrycie = od wierzchu rury do terenu. Strefa przemarzania to zwykle 1.0-1.4 m."""
    if dn_mm is None:
        return None
    wierzch_rury = rzedna_dna + dn_mm / 1000.0
    return round(rzedna_terenu - wierzch_rury, 3)
