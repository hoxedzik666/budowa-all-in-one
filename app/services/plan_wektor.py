"""Odczyt planow sytuacyjnych jako wektora - bez OCR.

Skad ta droga
-------------
"Plany sytuacyjne Scalone.pdf" ma wszystkie etykiety zamienione na krzywe, wiec
kodu obiektu nie da sie z niego przeczytac (patrz `plan_ocr.py` - proba OCR-u
skonczyla sie zerem trafien). Ale sam rysunek to nadal **czysty wektor**:
40-225 tysiecy sciezek na stronie, kazda z wlasnym kolorem i gruboscia kreski.

Kluczowa obserwacja: legenda na stronie 1 ma **zywy tekst** obok probek kresek.
Da sie wiec odczytac, jakim stylem narysowano kanalizacje deszczowa, i tym
stylem odfiltrowac ja z calego arkusza. Zamiast zgadywac, co jest napisane,
bierzemy to, co jest narysowane.

Czego ten modul NIE robi
------------------------
Nie przypisuje kodow obiektow. Wyciete polilinie to geometria bez nazw -
`D155` nie jest nigdzie zapisane. Kto ktory odcinek, wiadomo dopiero po
wskazaniu pozycji na mapie albo po georeferencji (`georef.py`).

Skala i jednostki
-----------------
Arkusze sa w prawdziwym formacie papieru, w skali 1:1000. Jeden punkt PDF to
1/72 cala = 0,352778 mm na papierze, czyli **0,352778 m w terenie**. To
przeliczenie jest scisle, nie przyblizone.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# PyMuPDF pod udawana nazwa - import odklada sie do pierwszego uzycia,
# zeby brak biblioteki (telefon) nie przewracal calej aplikacji.
# Szczegoly: app/services/opcjonalne.py
from app.services.opcjonalne import fitz

MM_NA_PUNKT = 25.4 / 72.0
TOL_KOLORU = 0.02
TOL_GRUBOSCI = 0.05

# Ile moga sie rozjechac konce dwoch kresek, zeby uznac je za jeden wierzcholek.
# 0,6 pt to ok. 21 cm w terenie - mniej niz srednica najmniejszej studni,
# a wiecej niz bledy zaokraglen w pliku.
SNAP_PT = 0.6

# Kilometraz jest jednym z niewielu zywych napisow na mapie: 124 wystapienia
# na 8 stronach. To domyka pytanie "z ktorego kilometra jest ten odcinek".
RE_KILOMETRAZ = re.compile(r"KM[:\s]*(\d+)\s*\+\s*(\d{3})")


@dataclass(frozen=True)
class StylKreski:
    """Kolor i grubosc kreski - w tym rysunku pelnia role nazwy warstwy."""

    nazwa: str
    kolor: tuple[float, float, float]
    grubosc: float

    def pasuje(self, sciezka: dict) -> bool:
        kolor = sciezka.get("color")
        if kolor is None or len(kolor) != 3:
            return False
        if any(abs(a - b) > TOL_KOLORU for a, b in zip(kolor, self.kolor)):
            return False
        return abs((sciezka.get("width") or 0.0) - self.grubosc) <= TOL_GRUBOSCI


# Odczytane z legendy na stronie 1 - probka kreski stoi tam obok zywego napisu.
STYLE = {
    "KD_GRAWITACYJNA": StylKreski("Kanalizacja deszczowa grawitacyjna",
                                  (0.0, 0.72157, 0.18039), 1.98),
}
STYL_DOMYSLNY = "KD_GRAWITACYJNA"


@dataclass
class Polilinia:
    """Ciag kresek o wspolnych koncach - jeden przewod miedzy rozgalezieniami."""

    punkty: list[tuple[float, float]]
    styl: str

    @property
    def dlugosc_pt(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.punkty, self.punkty[1:]))

    def dlugosc_m(self, skala: int = 1000) -> float:
        return round(self.dlugosc_pt * MM_NA_PUNKT * skala / 1000.0, 2)

    @property
    def poczatek(self) -> tuple[float, float]:
        return self.punkty[0]

    @property
    def koniec(self) -> tuple[float, float]:
        return self.punkty[-1]


@dataclass
class Etykieta:
    tekst: str
    x_pt: float
    y_pt: float
    kilometraz_m: float | None = None

    def to_dict(self) -> dict:
        return {"tekst": self.tekst, "x_pt": round(self.x_pt, 1),
                "y_pt": round(self.y_pt, 1), "kilometraz_m": self.kilometraz_m}


@dataclass
class SiecStrony:
    """Co udalo sie wyciac z jednej strony planu."""

    nr_strony: int
    szerokosc_pt: float
    wysokosc_pt: float
    skala: int
    polilinie: list[Polilinia] = field(default_factory=list)
    wezly: list[tuple[float, float]] = field(default_factory=list)
    etykiety: list[Etykieta] = field(default_factory=list)
    sciezek_na_stronie: int = 0

    @property
    def dlugosc_m(self) -> float:
        return round(sum(p.dlugosc_m(self.skala) for p in self.polilinie), 2)

    def podsumowanie(self) -> dict:
        return {
            "nr_strony": self.nr_strony,
            "skala": self.skala,
            "polilinii": len(self.polilinie),
            "wezlow": len(self.wezly),
            "dlugosc_m": self.dlugosc_m,
            "etykiet_kilometrazu": len(self.etykiety),
            "sciezek_na_stronie": self.sciezek_na_stronie,
        }


# ------------------------------------------------------------- wycinanie


def _przyciagnij(punkt, siatka: float = SNAP_PT) -> tuple[float, float]:
    return (round(punkt[0] / siatka) * siatka, round(punkt[1] / siatka) * siatka)


def zbierz_kreski(page: fitz.Page, styl: StylKreski) -> list[tuple]:
    """Wszystkie odcinki linii narysowane danym stylem."""
    kreski: list[tuple] = []
    for sciezka in page.get_drawings():
        if not styl.pasuje(sciezka):
            continue
        for element in sciezka["items"]:
            if element[0] != "l":
                continue
            a = _przyciagnij((element[1].x, element[1].y))
            b = _przyciagnij((element[2].x, element[2].y))
            if a != b:
                kreski.append((a, b))
    return kreski


def scal_polilinie(kreski: list[tuple], styl: str) -> tuple[list[Polilinia], list]:
    """Poskladaj kreski w polilinie i wskaz wezly sieci.

    Wierzcholek stopnia 2 to zwykle zalamanie trasy - idziemy przez niego dalej.
    Wierzcholek stopnia 1 (koniec przewodu) albo 3+ (rozgalezienie) konczy
    polilinie: to tam w terenie stoi studnia, wpust albo wylot.
    """
    sasiedzi: dict[tuple, set] = {}
    for a, b in kreski:
        sasiedzi.setdefault(a, set()).add(b)
        sasiedzi.setdefault(b, set()).add(a)

    wezly = [p for p, s in sasiedzi.items() if len(s) != 2]
    polilinie: list[Polilinia] = []
    uzyte: set = set()

    def idz(start, nastepny) -> list:
        trasa = [start, nastepny]
        poprzedni, biezacy = start, nastepny
        while len(sasiedzi[biezacy]) == 2:
            dalej = next(p for p in sasiedzi[biezacy] if p != poprzedni)
            if dalej == start:          # zamknieta petla
                break
            trasa.append(dalej)
            poprzedni, biezacy = biezacy, dalej
        return trasa

    for wezel in wezly:
        for sasiad in sasiedzi[wezel]:
            if (wezel, sasiad) in uzyte:
                continue
            trasa = idz(wezel, sasiad)
            uzyte.add((wezel, sasiad))
            uzyte.add((trasa[-1], trasa[-2]))
            polilinie.append(Polilinia(trasa, styl))

    # Obwody zamkniete nie maja zadnego wierzcholka o stopniu != 2 - trzeba je
    # zaczac od dowolnego punktu, inaczej przepadlyby bez sladu.
    odwiedzone = {p for pl in polilinie for p in pl.punkty}
    for punkt, s in sasiedzi.items():
        if punkt in odwiedzone or len(s) != 2:
            continue
        trasa = idz(punkt, next(iter(s)))
        polilinie.append(Polilinia(trasa, styl))
        odwiedzone.update(trasa)

    return polilinie, wezly


def etykiety_kilometrazu(page: fitz.Page) -> list[Etykieta]:
    """Zywe napisy `KM:5+814` - jedyne pewne odniesienie na mapie."""
    znalezione: list[Etykieta] = []
    widziane: set = set()
    for slowo in page.get_text("words"):
        dopasowanie = RE_KILOMETRAZ.search(slowo[4])
        if not dopasowanie:
            continue
        x = (slowo[0] + slowo[2]) / 2.0
        y = (slowo[1] + slowo[3]) / 2.0
        klucz = (slowo[4], round(x, 1), round(y, 1))
        if klucz in widziane:       # ten sam napis bywa w pliku kilka razy
            continue
        widziane.add(klucz)
        metry = int(dopasowanie.group(1)) * 1000 + int(dopasowanie.group(2))
        znalezione.append(Etykieta(slowo[4], x, y, float(metry)))
    return sorted(znalezione, key=lambda e: (e.kilometraz_m or 0, e.x_pt))


def odczytaj_skale(page: fitz.Page) -> int:
    from app.services.plan_ocr import odczytaj_skale as _skala

    return _skala(page)


def wytnij_siec(page: fitz.Page, nr_strony: int, styl: str = STYL_DOMYSLNY,
                min_dlugosc_m: float = 0.5) -> SiecStrony:
    """Wytnij z jednej strony sieć narysowaną danym stylem."""
    if styl not in STYLE:
        raise ValueError(f"Nie znam stylu {styl!r}. Dostepne: {sorted(STYLE)}")

    sciezki = page.get_drawings()
    kreski = zbierz_kreski(page, STYLE[styl])
    polilinie, wezly = scal_polilinie(kreski, styl)
    skala = odczytaj_skale(page)

    # Drobiazgi ponizej pol metra to zwykle groty strzalek i znaczniki,
    # nie przewody.
    polilinie = [p for p in polilinie if p.dlugosc_m(skala) >= min_dlugosc_m]

    return SiecStrony(
        nr_strony=nr_strony,
        szerokosc_pt=round(page.rect.width, 2),
        wysokosc_pt=round(page.rect.height, 2),
        skala=skala,
        polilinie=polilinie,
        wezly=wezly,
        etykiety=etykiety_kilometrazu(page),
        sciezek_na_stronie=len(sciezki),
    )


def wytnij_plan(sciezka: str | Path, strony: list[int] | None = None,
                styl: str = STYL_DOMYSLNY) -> list[SiecStrony]:
    doc = fitz.open(sciezka)
    try:
        numery = strony or list(range(1, doc.page_count + 1))
        return [wytnij_siec(doc[nr - 1], nr, styl)
                for nr in numery if 1 <= nr <= doc.page_count]
    finally:
        doc.close()
