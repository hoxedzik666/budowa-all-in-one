"""Serwer kafelkow dla planow sytuacyjnych.

Dlaczego kafelki, a nie jeden obrazek
-------------------------------------
Arkusz planu ma do 4900 x 1200 punktow. W rozdzielczosci, przy ktorej widac
numery studni, caly wyrenderowany naraz mialby kilkadziesiat megapikseli -
przegladarka by go nie przyjela, a serwer liczylby go kilkanascie sekund.
Kafelki renderuja **tylko to, co widac**: kwadrat 256 x 256 pikseli, i tylko
przy tym przyblizeniu, ktore jest akurat ustawione.

Dokument otwarty w pamieci, osobno dla kazdego watku
----------------------------------------------------
Otwarcie tego PDF-a to wczytanie do 225 tysiecy sciezek wektorowych. Poprzednia
wersja robila to przy **kazdym** zadaniu obrazka; przy kafelkach - kilkadziesiat
razy na jedno przesuniecie mapy - zoom bylby nie do uzycia. Dlatego dokument
zostaje otwarty i uzywany wielokrotnie.

Kazdy watek ma **wlasny** otwarty dokument, bo `fitz.Document` nie jest
bezpieczny przy jednoczesnym uzyciu przez kilka watkow.

Lista wyswietlania - to ona decyduje o plynnosci
------------------------------------------------
Samo trzymanie otwartego dokumentu nie wystarczylo: `page.get_pixmap()`
za kazdym razem na nowo przetwarza strumien tresci strony, wiec kafelek
kosztowal 0,43 s niezaleznie od tego, jak maly byl wycinek. Dwanascie kafelkow,
czyli jeden ekran, to bylo ponad 5 sekund.

`page.get_displaylist()` przetwarza strone **raz** (0,4 s) i zwraca gotowa liste
operacji rysunkowych. Kolejne kafelki renderuja sie juz z niej:

    12 kafelkow bez listy wyswietlania   5,18 s
    12 kafelkow z lista wyswietlania     0,21 s      (25 razy szybciej)

Czyli 17 ms na kafelek - tyle, ile trzeba, zeby mapa chodzila plynnie.
Listy trzymamy dla kilku ostatnio ogladanych stron; kazda zajmuje pamiec,
wiec liczba jest ograniczona.

Poziomy przyblizenia
--------------------
Poziom 0 to caly arkusz zmieszczony w jednym kafelku. Kazdy kolejny podwaja
rozdzielczosc. Kafelek zawsze pokrywa ten sam wycinek rysunku - zmienia sie
tylko gestosc pikseli, czyli w praktyce dpi renderowania.
"""
from __future__ import annotations

import hashlib
import math
import threading
from pathlib import Path

# PyMuPDF pod udawana nazwa - import odklada sie do pierwszego uzycia,
# zeby brak biblioteki (telefon) nie przewracal calej aplikacji.
# Szczegoly: app/services/opcjonalne.py
from app.services.opcjonalne import fitz

BOK_KAFELKA = 256
MAX_ZOOM = 7            # przy arkuszu 4900 pt to ok. 1500 dpi - grubo powyzej sensu
DPI_BAZOWE = 72.0

# Skala rysunku 1:1000 -> 1 pt = 0,352778 m w terenie.
METRY_NA_PUNKT = 25.4 / 72.0

# Ile list wyswietlania trzymac naraz w jednym watku. Kazda to cala strona
# rozlozona na operacje rysunkowe - przy 225 tysiacach sciezek to niemalo
# pamieci, a i tak oglada sie zwykle jeden arkusz naraz.
MAX_LIST_WYSWIETLANIA = 3

_lokalne = threading.local()


def dokument(sciezka: str | Path) -> fitz.Document:
    """Otwarty PDF - osobny egzemplarz dla kazdego watku."""
    klucz = str(sciezka)
    otwarte = getattr(_lokalne, "dokumenty", None)
    if otwarte is None:
        otwarte = _lokalne.dokumenty = {}
    doc = otwarte.get(klucz)
    if doc is None or doc.is_closed:
        doc = fitz.open(klucz)
        otwarte[klucz] = doc
    return doc


def zamknij_wszystkie() -> None:
    """Zamknij dokumenty otwarte przez biezacy watek."""
    listy = getattr(_lokalne, "listy", None) or {}
    listy.clear()
    otwarte = getattr(_lokalne, "dokumenty", None) or {}
    for doc in otwarte.values():
        if not doc.is_closed:
            doc.close()
    otwarte.clear()


def lista_wyswietlania(sciezka: str | Path, nr_strony: int):
    """Strona rozlozona raz na operacje rysunkowe - sedno plynnosci zoomu."""
    klucz = (str(sciezka), nr_strony)
    listy = getattr(_lokalne, "listy", None)
    if listy is None:
        listy = _lokalne.listy = {}
    gotowa = listy.get(klucz)
    if gotowa is None:
        gotowa = dokument(sciezka)[nr_strony - 1].get_displaylist()
        listy[klucz] = gotowa
        while len(listy) > MAX_LIST_WYSWIETLANIA:
            listy.pop(next(iter(listy)))
    return gotowa


def rozmiar_strony(sciezka: str | Path, nr_strony: int) -> tuple[float, float]:
    strona = dokument(sciezka)[nr_strony - 1]
    return strona.rect.width, strona.rect.height


def liczba_stron(sciezka: str | Path) -> int:
    return dokument(sciezka).page_count


def skala_zoomu(szerokosc_pt: float, wysokosc_pt: float, zoom: int) -> float:
    """Ile punktow rysunku przypada na jeden piksel przy danym przyblizeniu."""
    bok_pt = max(szerokosc_pt, wysokosc_pt)
    return bok_pt / (BOK_KAFELKA * (2 ** zoom))


def zakres_kafelkow(szerokosc_pt: float, wysokosc_pt: float, zoom: int) -> tuple[int, int]:
    pt_na_piksel = skala_zoomu(szerokosc_pt, wysokosc_pt, zoom)
    return (math.ceil(szerokosc_pt / (pt_na_piksel * BOK_KAFELKA)),
            math.ceil(wysokosc_pt / (pt_na_piksel * BOK_KAFELKA)))


def renderuj_kafelek(sciezka: str | Path, nr_strony: int, zoom: int,
                     kol: int, wiersz: int) -> bytes:
    """Jeden kafelek 256 x 256 pikseli."""
    doc = dokument(sciezka)
    if not 1 <= nr_strony <= doc.page_count:
        raise ValueError(f"Plan ma {doc.page_count} stron, nie ma strony {nr_strony}.")
    strona = doc[nr_strony - 1]
    szerokosc, wysokosc = strona.rect.width, strona.rect.height

    pt_na_piksel = skala_zoomu(szerokosc, wysokosc, zoom)
    bok_pt = BOK_KAFELKA * pt_na_piksel
    clip = fitz.Rect(kol * bok_pt, wiersz * bok_pt,
                     (kol + 1) * bok_pt, (wiersz + 1) * bok_pt)

    # Kafelek poza arkuszem - Leaflet i tak o niego zapyta na brzegach.
    if clip.x0 >= szerokosc or clip.y0 >= wysokosc:
        return _pusty_kafelek()

    # Skale zadajemy macierza, a nie parametrem `dpi`, bo dpi musi byc
    # calkowite - przy ulamkowym przeliczeniu kafelki rozjezdzalyby sie
    # o czesc piksela i na stykach bylyby widoczne szwy.
    macierz = fitz.Matrix(1.0 / pt_na_piksel, 1.0 / pt_na_piksel)
    przyciety = clip & strona.rect
    pix = lista_wyswietlania(sciezka, nr_strony).get_pixmap(
        matrix=macierz, clip=przyciety, alpha=False)

    if pix.width == BOK_KAFELKA and pix.height == BOK_KAFELKA:
        return pix.tobytes("png")

    # Kafelek brzegowy jest mniejszy niz pelny - dopelniamy bialym tlem,
    # zeby Leaflet nie rozciagal obrazu.
    pelny = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, BOK_KAFELKA, BOK_KAFELKA), False)
    pelny.clear_with(255)
    pix.set_origin(0, 0)
    pelny.copy(pix, fitz.IRect(0, 0, min(pix.width, BOK_KAFELKA),
                               min(pix.height, BOK_KAFELKA)))
    return pelny.tobytes("png")


_PUSTY: bytes | None = None


def _pusty_kafelek() -> bytes:
    global _PUSTY
    if _PUSTY is None:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, BOK_KAFELKA, BOK_KAFELKA), False)
        pix.clear_with(255)
        _PUSTY = pix.tobytes("png")
    return _PUSTY


# ------------------------------------------------------------------- cache


def nazwa_kafelka(nr_strony: int, zoom: int, kol: int, wiersz: int) -> str:
    return f"s{nr_strony:02d}-z{zoom}-{kol}-{wiersz}.png"


def sprzataj(katalog: Path, limit_mb: int) -> int:
    """Utrzymaj cache ponizej limitu, kasujac najdawniej uzywane kafelki.

    Bez tego katalog rosnie bez konca: samo obejrzenie jednego arkusza w pelnym
    przyblizeniu to kilka tysiecy kafelkow.
    """
    if not katalog.exists():
        return 0
    pliki = sorted(katalog.glob("*.png"), key=lambda p: p.stat().st_atime)
    razem = sum(p.stat().st_size for p in pliki)
    limit = limit_mb * 1024 * 1024
    usuniete = 0
    for plik in pliki:
        if razem <= limit:
            break
        rozmiar = plik.stat().st_size
        try:
            plik.unlink()
        except OSError:
            continue
        razem -= rozmiar
        usuniete += 1
    return usuniete


def odcisk_pliku(sciezka: Path) -> str:
    """Krotki odcisk pliku - zmiana dokumentu uniewaznia cache kafelkow."""
    stan = sciezka.stat()
    return hashlib.sha1(f"{sciezka.name}|{stan.st_size}|{int(stan.st_mtime)}"
                        .encode()).hexdigest()[:10]
