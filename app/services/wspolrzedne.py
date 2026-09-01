"""Przeliczenie pozycji z telefonu na wspolrzedne planu.

Po co
-----
Telefon podaje pozycje w WGS84 (stopnie szerokosci i dlugosci). Plany sa
w **PL-2000 strefa 5 (EPSG:2176)**, a georeferencja z etapu 4 przelicza ten
uklad na punkty rysunku. Brakowalo tylko pierwszego ogniwa:

    GPS (WGS84)  ──►  PL-2000/5  ──►  punkt na arkuszu
                 tu           georef.py

Dlaczego pyproj, a nie wlasny wzor
----------------------------------
Odwzorowanie Gaussa-Krugera da sie zaimplementowac w kilkudziesieciu liniach
i kusi, zeby nie dokladac zaleznosci. Ale to jest transformacja geodezyjna:
blad w szostym miejscu po przecinku wspolczynnika daje kilkanascie metrow
w terenie i nie widac go inaczej niz przez porownanie z punktem kontrolnym.
Biblioteka ma to sprawdzone i ma tez poprawna definicje elipsoidy GRS80.

Dokladnosc
----------
GPS w telefonie ma 3-10 m. To **wystarcza, zeby znalezc studnie, i nie
wystarcza do tyczenia** - roznica miedzy WGS84 a ETRS89, na ktorym opiera sie
PL-2000, to w Polsce okolo 0,7 m i przy tym bledzie pomiaru jest bez znaczenia.
Interfejs ma pokazywac dokladnosc zawsze, zeby nikt nie potraktowal odczytu
powazniej, niz nalezy.
"""
from __future__ import annotations

from functools import lru_cache

# PL-2000 strefa 5: poludnik osiowy 15 st. E, EPSG:2176. Zgodne z tabelka
# na planach ("2000/15") i z plikiem osnowy (X ok. 5,77 mln, Y ok. 5,50 mln).
EPSG_PL2000_S5 = 2176
EPSG_WGS84 = 4326

# Ponizej tej dokladnosci odczyt nadaje sie tylko do zgrubnej orientacji.
PROG_DOKLADNOSCI_M = 15.0

# Zakres, w ktorym w ogole moze lezec ta budowa. Punkt spoza niego oznacza
# najczesciej wlaczony w telefonie "GPS testowy" albo pomylone lat/lon.
ZAKRES_SZEROKOSCI = (49.0, 55.0)
ZAKRES_DLUGOSCI = (13.0, 17.5)


@lru_cache(maxsize=2)
def _przelicznik(z_epsg: int, na_epsg: int):
    """Transformator pyproj. Tworzony raz - jego budowa nie jest darmowa."""
    from app.services.opcjonalne import wymagaj

    # W Termuxie pyproj bywa nieobecny (wymaga biblioteki PROJ). `wymagaj`
    # zamienia ImportError na komunikat, ktory mowi, ze GPS nie przeliczy sie
    # na PL-2000/5 - reszta narzedzia dziala dalej.
    Transformer = wymagaj("pyproj").Transformer

    # always_xy=False: trzymamy sie kolejnosci z definicji ukladu, czyli
    # (szerokosc, dlugosc) dla WGS84 i (polnoc, wschod) dla PL-2000.
    return Transformer.from_crs(z_epsg, na_epsg, always_xy=False)


def gps_na_pl2000(szerokosc: float, dlugosc: float) -> tuple[float, float]:
    """WGS84 (stopnie) -> PL-2000/5. Zwraca (X polnoc, Y wschod)."""
    polnoc, wschod = _przelicznik(EPSG_WGS84, EPSG_PL2000_S5).transform(
        szerokosc, dlugosc)
    return round(polnoc, 3), round(wschod, 3)


def pl2000_na_gps(polnoc: float, wschod: float) -> tuple[float, float]:
    """PL-2000/5 -> WGS84. Uzywane do sprawdzenia poprawnosci na osnowie."""
    szerokosc, dlugosc = _przelicznik(EPSG_PL2000_S5, EPSG_WGS84).transform(
        polnoc, wschod)
    return round(szerokosc, 7), round(dlugosc, 7)


def sprawdz_pozycje(szerokosc: float, dlugosc: float,
                    dokladnosc_m: float | None = None) -> str | None:
    """Co jest nie tak z tym odczytem. None = nic.

    Osobna funkcja, bo o kazdej z tych rzeczy trzeba powiedziec inaczej,
    a zadna nie jest powodem, zeby odmowic odpowiedzi.
    """
    if not ZAKRES_SZEROKOSCI[0] <= szerokosc <= ZAKRES_SZEROKOSCI[1] \
            or not ZAKRES_DLUGOSCI[0] <= dlugosc <= ZAKRES_DLUGOSCI[1]:
        return (f"Pozycja {szerokosc:.4f}, {dlugosc:.4f} leży poza Polską — "
                "sprawdź, czy telefon nie ma włączonej pozycji testowej.")

    if dokladnosc_m is not None and dokladnosc_m > PROG_DOKLADNOSCI_M:
        return (f"Dokładność GPS to {dokladnosc_m:.0f} m — to za mało nawet do "
                "orientacji. Wyjdź spod drzew i poczekaj chwilę.")
    return None
