"""Wycinanie fragmentu oryginalnego rysunku z "Profile Scalone.pdf".

Po co
-----
Aplikacja podaje liczby wyciagniete z rysunku przez parser. Zeby dalo sie im
zaufac, musi byc jak sprawdzic - postawic obok siebie liczbe z ekranu i ten sam
fragment oryginalu. Ten modul wycina z arkusza dokladnie te czesc, ktorej
dotyczy pytanie.

Dlaczego dwa pasy, a nie jeden
------------------------------
Profil na arkuszu ma srednio 74 punkty szerokosci - 26 mm. Sam w sobie jest
nieczytelny: kolumna liczb bez podpisow. Podpisy pasm (RZEDNA DNA KANALU,
SPADKI, DLUGOSCI, HEKTOMETRY...) stoja raz na cala strone, przy jej lewej
krawedzi. Dlatego wycinek sklada sie z dwoch pasow tej samej strony:

    ┌──────────────┬──────────────────────┐
    │ OZNACZENIE   │                      │
    │ RZĘDNA DNA   │   rysunek profilu    │
    │ SPADKI, DŁUG.│   + kolumny wezlow   │
    │ HEKTOMETRY   │                      │
    └──────────────┴──────────────────────┘
      pas legendy         pas profilu

Kiedy to dziala
---------------
Wylacznie na zadanie. Konwersja PDF jest kosztowna, wiec nic nie renderuje sie
"na wszelki wypadek" - dopiero po klinieciu, a wynik ladzie w cache.

Format
------
Skladanie idzie przez `show_pdf_page`, czyli **kopiowanie wektora**, nie obrazka.
Wynikowy PDF da sie przybliżyc bez utraty ostrosci i wydrukowac w jakosci
oryginalu. PNG powstaje dopiero z tego PDF-a, do pokazania na stronie.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

# PyMuPDF pod udawana nazwa - import odklada sie do pierwszego uzycia,
# zeby brak biblioteki (telefon) nie przewracal calej aplikacji.
# Szczegoly: app/services/opcjonalne.py
from app.services.opcjonalne import fitz

# Podpisy pasm tabeli. Wystarczy trafic kilka - bierzemy obrys wszystkich.
NAGLOWKI_PASM = (
    "OZNACZENIE PROFILU",
    "POZIOM PORÓWNAWCZY",
    "RZĘDNA TERENU",
    "RZĘDNA DNA",
    "RZĘDNA OSI",
    "ZAGŁĘBIENIE",
    "SPADKI",
    "ŚREDNICA",
    "ODLEGŁOŚCI",
    "HEKTOMETRY",
)

MARGINES_PT = 26.0          # ile dorysowac po bokach profilu
MIN_SZEROKOSC_PT = 110.0    # profile 2-wezlowe bywaja weższe niz to czytelne
ODSTEP_PT = 10.0            # przerwa miedzy pasem legendy a pasem profilu
LUZ_LEGENDY_PT = 8.0
DPI_PODGLAD = 150


@dataclass
class Wycinek:
    """Gotowy fragment rysunku wraz z opisem, skad pochodzi."""

    pdf: bytes
    nr_strony: int
    x_od: float
    x_do: float
    szerokosc_pt: float
    wysokosc_pt: float
    z_legenda: bool

    def png(self, dpi: int = DPI_PODGLAD) -> bytes:
        doc = fitz.open(stream=self.pdf, filetype="pdf")
        try:
            return doc[0].get_pixmap(dpi=dpi).tobytes("png")
        finally:
            doc.close()


def znajdz_pas_legendy(page: fitz.Page) -> fitz.Rect | None:
    """Obrys kolumny z podpisami pasm tabeli.

    Podpisy sa poziome i stoja przy lewej krawedzi arkusza. Szukamy ich po
    tresci, a nie po stalej wspolrzednej, bo kazda strona ma inny format.
    """
    obrys: fitz.Rect | None = None
    for blok in page.get_text("dict")["blocks"]:
        for linia in blok.get("lines", []):
            for span in linia.get("spans", []):
                tekst = (span.get("text") or "").strip().upper()
                if not any(tekst.startswith(n) for n in NAGLOWKI_PASM):
                    continue
                prostokat = fitz.Rect(span["bbox"])
                obrys = prostokat if obrys is None else obrys | prostokat
    if obrys is None:
        return None
    return fitz.Rect(
        max(obrys.x0 - LUZ_LEGENDY_PT, 0.0),
        max(obrys.y0 - LUZ_LEGENDY_PT, 0.0),
        obrys.x1 + LUZ_LEGENDY_PT,
        min(obrys.y1 + LUZ_LEGENDY_PT, page.rect.y1),
    )


def zakres_pionowy(page: fitz.Page, lewa: float, prawa: float) -> tuple[float, float]:
    """Gdzie w pionie naprawde cos jest.

    Arkusz profili ma 1684 punkty wysokosci, a pojedynczy profil zajmuje z tego
    dolna trzecia. Bez przyciecia wycinek to w wiekszosci pusty papier, na
    ktorym rysunek robi sie nieczytelnie maly.
    """
    # Uwaga: liczy sie zawieranie, nie przeciecie. Ramka arkusza i pionowe
    # linie tabeli biegna przez cala wysokosc strony i przecinaja kazde pasmo -
    # gdyby je liczyc, przyciecie nigdy nic by nie ucielo.
    obrys: fitz.Rect | None = None

    def w_pasmie(prostokat: fitz.Rect) -> bool:
        return (not prostokat.is_empty
                and prostokat.x0 >= lewa - 2.0
                and prostokat.x1 <= prawa + 2.0)

    for sciezka in page.get_drawings():
        if w_pasmie(sciezka["rect"]):
            obrys = sciezka["rect"] if obrys is None else obrys | sciezka["rect"]

    for slowo in page.get_text("words"):
        prostokat = fitz.Rect(slowo[:4])
        if w_pasmie(prostokat):
            obrys = prostokat if obrys is None else obrys | prostokat

    if obrys is None:
        return 0.0, page.rect.y1
    return (max(obrys.y0 - MARGINES_PT, 0.0),
            min(obrys.y1 + MARGINES_PT, page.rect.y1))


def _zakres_poziomy(x_od: float, x_do: float, page: fitz.Page) -> tuple[float, float]:
    """Poszerz waski profil, zeby wycinek dalo sie przeczytac.

    Cztery profile w tej dokumentacji maja zerowa szerokosc obrysu - bez tego
    zabezpieczenia wyszedlby z nich pusty obrazek.
    """
    x_od, x_do = min(x_od, x_do), max(x_od, x_do)
    lewa = x_od - MARGINES_PT
    prawa = x_do + MARGINES_PT
    if prawa - lewa < MIN_SZEROKOSC_PT:
        srodek = (lewa + prawa) / 2.0
        lewa = srodek - MIN_SZEROKOSC_PT / 2.0
        prawa = srodek + MIN_SZEROKOSC_PT / 2.0
    return max(lewa, 0.0), min(prawa, page.rect.x1)


def wytnij(sciezka: str | Path, nr_strony: int, x_od: float, x_do: float,
           z_legenda: bool = True) -> Wycinek:
    """Zloz wycinek: pas legendy + pas profilu, oba z tej samej strony."""
    zrodlo = fitz.open(sciezka)
    try:
        if not 1 <= nr_strony <= zrodlo.page_count:
            raise ValueError(f"Plik ma {zrodlo.page_count} stron, nie ma strony {nr_strony}.")
        strona = zrodlo[nr_strony - 1]

        lewa, prawa = _zakres_poziomy(x_od, x_do, strona)
        clip_legendy = znajdz_pas_legendy(strona) if z_legenda else None

        # Wspolny zakres pionowy dla obu pasow - inaczej podpisy pasm nie
        # staneleby w jednej linii z liczbami, ktore opisuja.
        gora, dol = zakres_pionowy(strona, lewa, prawa)
        if clip_legendy is not None:
            gora = min(gora, clip_legendy.y0)
            dol = max(dol, clip_legendy.y1)
        wysokosc = dol - gora

        clip_profilu = fitz.Rect(lewa, gora, prawa, dol)
        if clip_legendy is not None:
            clip_legendy = fitz.Rect(clip_legendy.x0, gora, clip_legendy.x1, dol)

        szer_legendy = clip_legendy.width if clip_legendy else 0.0
        odstep = ODSTEP_PT if clip_legendy else 0.0
        szerokosc = szer_legendy + odstep + clip_profilu.width

        wynik = fitz.open()
        karta = wynik.new_page(width=szerokosc, height=wysokosc)

        if clip_legendy is not None:
            karta.show_pdf_page(
                fitz.Rect(0, 0, szer_legendy, wysokosc), zrodlo, nr_strony - 1,
                clip=clip_legendy,
            )
            # Cienka kreska oddzielajaca podpisy od danych - inaczej wycinek
            # wyglada jak jeden ciagly fragment rysunku, ktorym nie jest.
            x = szer_legendy + odstep / 2.0
            ksztalt = karta.new_shape()
            ksztalt.draw_line(fitz.Point(x, 0), fitz.Point(x, wysokosc))
            ksztalt.finish(color=(0.7, 0.7, 0.7), width=0.6, dashes="[3 3] 0")
            ksztalt.commit()

        karta.show_pdf_page(
            fitz.Rect(szer_legendy + odstep, 0, szerokosc, wysokosc),
            zrodlo, nr_strony - 1, clip=clip_profilu,
        )

        dane = wynik.tobytes(garbage=3, deflate=True)
        wynik.close()
        return Wycinek(
            pdf=dane, nr_strony=nr_strony, x_od=lewa, x_do=prawa,
            szerokosc_pt=round(szerokosc, 1), wysokosc_pt=round(wysokosc, 1),
            z_legenda=clip_legendy is not None,
        )
    finally:
        zrodlo.close()


# ------------------------------------------------------------------ cache


def klucz_cache(nr_strony: int, x_od: float, x_do: float, z_legenda: bool,
                rozszerzenie: str, dpi: int = 0) -> str:
    surowy = f"{nr_strony}|{x_od:.1f}|{x_do:.1f}|{int(z_legenda)}|{dpi}"
    return hashlib.sha1(surowy.encode()).hexdigest()[:20] + rozszerzenie


def z_cache(katalog: Path, nazwa: str) -> bytes | None:
    plik = katalog / nazwa
    return plik.read_bytes() if plik.exists() else None


def do_cache(katalog: Path, nazwa: str, dane: bytes) -> None:
    katalog.mkdir(parents=True, exist_ok=True)
    (katalog / nazwa).write_bytes(dane)
