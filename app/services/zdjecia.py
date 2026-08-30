"""Przyjmowanie zdjec z telefonu.

Zdjecie z telefonu ma kilkanascie megabajtow i 4000 pikseli szerokosci.
Do udokumentowania wykopu wystarcza 1600 px, a roznicy nikt nie zobaczy -
za to przy 30 zdjeciach dziennie roznica w miejscu na dysku i w czasie
wysylki przez slaby zasieg jest ogromna.

Dlatego kazde zdjecie przechodzi przez ten modul: zmniejszenie, obrot wedlug
EXIF i zapis w dwoch rozmiarach.
"""
from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

# Dluzszy bok zapisywanego zdjecia. 1600 px to czytelny napis na lacie
# i rozroznialne uziarnienie podsypki - wiecej nie wnosi nic.
BOK_ZDJECIA = 1600
JAKOSC = 82

DOZWOLONE_TYPY = {"image/jpeg", "image/png", "image/webp"}
DOZWOLONE_ROZSZERZENIA = {".jpg", ".jpeg", ".png", ".webp"}


class BladZdjecia(Exception):
    """Powod, dla ktorego pliku nie da sie przyjac - do pokazania czlowiekowi."""


def _katalog_miesiaca(katalog_glowny: Path) -> tuple[Path, str]:
    """Zdjecia w podkatalogach miesiecznych.

    Jeden plaski katalog z kilkoma tysiacami plikow robi sie nieporeczny przy
    kopii zapasowej i przy szukaniu czegokolwiek recznie.
    """
    wzgledny = date.today().strftime("%Y-%m")
    sciezka = katalog_glowny / wzgledny
    sciezka.mkdir(parents=True, exist_ok=True)
    return sciezka, wzgledny


def zapisz(plik, katalog_glowny: str | Path) -> dict:
    """Przyjmij plik z formularza. Zwraca dane do zapisania w bazie.

    Rzuca `BladZdjecia` z powodem po polsku - komunikat idzie wprost do
    uzytkownika, wiec nie moze byc slademstosu.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    nazwa = (getattr(plik, "filename", "") or "").lower()
    rozszerzenie = Path(nazwa).suffix
    typ = (getattr(plik, "mimetype", "") or "").lower()

    if typ not in DOZWOLONE_TYPY and rozszerzenie not in DOZWOLONE_ROZSZERZENIA:
        raise BladZdjecia(
            "To nie jest zdjęcie. Przyjmuję pliki JPG, PNG i WEBP.")

    try:
        obraz = Image.open(plik.stream)
        # Telefon zapisuje orientacje w EXIF zamiast obracac piksele. Bez tego
        # polowa zdjec lezy na boku.
        obraz = ImageOps.exif_transpose(obraz)
        obraz = obraz.convert("RGB")
    except (UnidentifiedImageError, OSError) as blad:
        raise BladZdjecia("Nie udało się otworzyć tego pliku jako zdjęcia.") from blad

    katalog, wzgledny = _katalog_miesiaca(Path(katalog_glowny))
    trzon = f"{date.today().strftime('%d')}-{secrets.token_hex(6)}"

    pelne = obraz.copy()
    pelne.thumbnail((BOK_ZDJECIA, BOK_ZDJECIA), Image.LANCZOS)
    nazwa_pelnego = f"{trzon}.jpg"
    pelne.save(katalog / nazwa_pelnego, "JPEG", quality=JAKOSC, optimize=True)

    from app.models.zdjecie import BOK_MINIATURY

    mini = obraz.copy()
    mini.thumbnail((BOK_MINIATURY, BOK_MINIATURY), Image.LANCZOS)
    nazwa_mini = f"{trzon}-mini.jpg"
    mini.save(katalog / nazwa_mini, "JPEG", quality=75, optimize=True)

    return {
        "plik": f"{wzgledny}/{nazwa_pelnego}",
        "miniatura": f"{wzgledny}/{nazwa_mini}",
        "szerokosc_px": pelne.width,
        "wysokosc_px": pelne.height,
        "rozmiar_b": (katalog / nazwa_pelnego).stat().st_size,
    }


def usun_pliki(zdjecie, katalog_glowny: str | Path) -> None:
    """Skasuj pliki z dysku. Baza to osobna sprawa."""
    katalog = Path(katalog_glowny)
    for wzgledna in (zdjecie.plik, zdjecie.miniatura):
        if not wzgledna:
            continue
        try:
            (katalog / wzgledna).unlink(missing_ok=True)
        except OSError:
            # Brak pliku nie moze blokowac usuniecia wpisu z bazy.
            pass
