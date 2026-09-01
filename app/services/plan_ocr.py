"""Odzyskiwanie etykiet z planow sytuacyjnych przez OCR.

Dlaczego w ogole OCR
--------------------
"Plany sytuacyjne Scalone.pdf" to rysunek wektorowy, ale **wszystkie napisy na
mapie sa zamienione na krzywe**. W calym 18-stronicowym pliku jest 667 unikalnych
slow: legenda, tabelka rysunkowa, nazwy miejscowosci i kilometraz drenow. Kodu
zadnego obiektu (`D155`, `Wyl101`, `Wp65`) nie da sie odczytac jako tekst.
Zadny z dostarczonych plikow nie ma tez wspolrzednych X/Y obiektow.

Jak to robimy
-------------
1. Renderujemy strone **kafelkami** - cala strona w 300 dpi to ok. 124 Mpx,
   za duzo na jedno przejscie tesseracta.
2. Tryb `--psm 11` (tekst rozproszony) - wlasciwy dla rysunku CAD, gdzie napisy
   sa rozrzucone, a nie ulozone w wiersze.
3. Wynik filtrujemy wzorcem kodu, a potem stosujemy **twarde ograniczenie:
   przyjmujemy wylacznie kody, ktore juz istnieja w bazie**. Nie odkrywamy nowych
   obiektow - lokalizujemy znane. To odcina wiekszosc bledow OCR.
4. Kazdy trafiony kod dostaje **poziom pewnosci** z tesseracta i trafia do
   `plan_location`. Nic nie jest podawane jako pewnik.

Czego ta metoda nie zrobi
-------------------------
Na gestym rysunku czesci etykiet OCR nie odczyta wcale, a czesc pomyli
(`D155` / `D156`, `0` / `O`). Dlatego wynik jest zawsze opatrzony pewnoscia,
a interfejs odroznia lokalizacje potwierdzona od domniemanej.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# PyMuPDF pod udawana nazwa - import odklada sie do pierwszego uzycia,
# zeby brak biblioteki (telefon) nie przewracal calej aplikacji.
# Szczegoly: app/services/opcjonalne.py
from app.services.opcjonalne import fitz

# Kod obiektu tak, jak moze go zwrocic OCR - z typowymi przekreceniami.
# Bez wariantu "0" na poczatku: cyfra zero mylona z litera O zamieniala
# zwykle wymiary z rysunku (0.6, 0.04) na nieistniejace osadniki O6, O4.
RE_KOD_OCR = re.compile(r"^(Wyl|WYL|SEP|Wp|WP|Tr|TR|KT|D|O)(\d{1,3})([a-z]?)$")
RE_REPER_OCR = re.compile(r"^[o0O]\s?(\d{1,3})([a-z]?)$")
RE_SKALA = re.compile(r"1\s*:\s*(\d{2,5})")

DPI = 300
KAFELEK_PX = 2200          # bok kafelka w pikselach
ZAKLADKA_PX = 200          # zakladka, zeby etykieta na styku nie przepadla
PROG_PEWNOSCI = 60.0       # ponizej tego nawet nie zapisujemy
KONFIG_TESSERACT = "--oem 1 --psm 11 -c tessedit_char_whitelist=0123456789abcdeoglpstwyDKOPSTWYL.-"


@dataclass
class TrafienieOCR:
    tekst: str
    kod: str
    x_pt: float
    y_pt: float
    pewnosc: float

    def to_dict(self) -> dict:
        return {"tekst": self.tekst, "kod": self.kod, "x_pt": round(self.x_pt, 1),
                "y_pt": round(self.y_pt, 1), "pewnosc": round(self.pewnosc, 1)}


@dataclass
class WynikStrony:
    nr_strony: int
    szerokosc_pt: float
    wysokosc_pt: float
    skala: int = 1000
    trafienia: list[TrafienieOCR] = field(default_factory=list)
    surowych_tokenow: int = 0
    uwagi: list[str] = field(default_factory=list)


def normalizuj_kod(tekst: str) -> str | None:
    """Zamien odczyt OCR na kanoniczny kod obiektu albo zwroc None."""
    t = tekst.strip().replace(" ", "").replace("_", "")
    m = RE_KOD_OCR.match(t)
    if not m:
        return None
    prefiks, numer, litera = m.group(1), m.group(2), m.group(3)
    mapa = {"wyl": "Wyl", "sep": "SEP", "wp": "Wp", "tr": "Tr", "kt": "KT",
            "d": "D", "o": "O"}
    return f"{mapa.get(prefiks.lower(), prefiks)}{int(numer)}{litera}"


def odczytaj_skale(page) -> int:
    """Skala rysunku z tabelki - potrzebna do przeliczenia punktow na metry."""
    skale = [int(m) for m in RE_SKALA.findall(page.get_text())]
    sensowne = [s for s in skale if 100 <= s <= 5000]
    if not sensowne:
        return 1000
    # Na stronie bywa kilka skal (rysunek + wstawki); bierzemy najczestsza.
    return max(set(sensowne), key=sensowne.count)


def _kafelki(szer_px: int, wys_px: int):
    """Podziel obraz strony na kafelki z zakladka."""
    krok = KAFELEK_PX - ZAKLADKA_PX
    for gy in range(0, max(wys_px - ZAKLADKA_PX, 1), krok):
        for gx in range(0, max(szer_px - ZAKLADKA_PX, 1), krok):
            yield gx, gy, min(gx + KAFELEK_PX, szer_px), min(gy + KAFELEK_PX, wys_px)


def ocr_strony(page, nr_strony: int, dopuszczalne_kody: set[str],
               dpi: int = DPI) -> WynikStrony:
    """Przeleć jedna strone OCR-em i zwroc trafienia ograniczone do znanych kodow."""
    from app.services.opcjonalne import wymagaj

    pytesseract = wymagaj("pytesseract")
    Image = wymagaj("PIL.Image")

    wynik = WynikStrony(
        nr_strony=nr_strony,
        szerokosc_pt=round(page.rect.width, 2),
        wysokosc_pt=round(page.rect.height, 2),
        skala=odczytaj_skale(page),
    )
    skala_px = dpi / 72.0
    szer_px = int(page.rect.width * skala_px)
    wys_px = int(page.rect.height * skala_px)

    najlepsze: dict[str, TrafienieOCR] = {}
    for x0, y0, x1, y1 in _kafelki(szer_px, wys_px):
        clip = fitz.Rect(x0 / skala_px, y0 / skala_px, x1 / skala_px, y1 / skala_px)
        pix = page.get_pixmap(dpi=dpi, clip=clip)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        dane = pytesseract.image_to_data(
            img, lang="pol+eng", config=KONFIG_TESSERACT,
            output_type=pytesseract.Output.DICT,
        )
        for i, tekst in enumerate(dane["text"]):
            tekst = (tekst or "").strip()
            if not tekst:
                continue
            wynik.surowych_tokenow += 1
            try:
                pewnosc = float(dane["conf"][i])
            except (TypeError, ValueError):
                continue
            if pewnosc < PROG_PEWNOSCI:
                continue
            kod = normalizuj_kod(tekst)
            if kod is None or kod not in dopuszczalne_kody:
                continue

            # Srodek slowa w pikselach kafelka -> punkty PDF calej strony.
            sx = dane["left"][i] + dane["width"][i] / 2
            sy = dane["top"][i] + dane["height"][i] / 2
            x_pt = clip.x0 + sx / skala_px
            y_pt = clip.y0 + sy / skala_px

            poprzednie = najlepsze.get(kod)
            if poprzednie is None or pewnosc > poprzednie.pewnosc:
                najlepsze[kod] = TrafienieOCR(tekst, kod, x_pt, y_pt, pewnosc)

    wynik.trafienia = sorted(najlepsze.values(), key=lambda t: t.kod)
    if not wynik.trafienia:
        wynik.uwagi.append("OCR nie odczytal zadnego znanego kodu na tej stronie.")
    return wynik


def ocr_planow(sciezka: str | Path, dopuszczalne_kody: set[str],
               strony: list[int] | None = None, dpi: int = DPI) -> list[WynikStrony]:
    """Przeleć caly plik. `strony` numerowane od 1; None = wszystkie."""
    doc = fitz.open(sciezka)
    numery = strony or list(range(1, doc.page_count + 1))
    wyniki = []
    for nr in numery:
        if not 1 <= nr <= doc.page_count:
            continue
        wyniki.append(ocr_strony(doc[nr - 1], nr, dopuszczalne_kody, dpi))
    doc.close()
    return wyniki


def tesseract_dostepny() -> tuple[bool, str]:
    """Sprawdz, czy da sie w ogole uruchomic OCR - zanim uzytkownik czeka 10 minut."""
    try:
        import pytesseract
        wersja = str(pytesseract.get_tesseract_version())
        return True, wersja
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
