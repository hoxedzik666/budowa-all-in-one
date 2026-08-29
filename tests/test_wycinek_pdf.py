"""Wycinek oryginalnego rysunku - dowod, ze liczbom w aplikacji mozna ufac.

Wycinek ma sens tylko wtedy, gdy da sie go przeczytac. Stad testy pilnuja
trzech rzeczy: podpisow pasm (bez nich zostaja same liczby bez znaczenia),
minimalnej szerokosci (cztery profile w tej dokumentacji maja zerowy obrys)
i przyciecia w pionie (arkusz jest wysoki na 1684 pt, profil zajmuje trzecia
czesc - reszta to pusty papier).
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.services.wycinek_pdf import (
    MIN_SZEROKOSC_PT,
    klucz_cache,
    wytnij,
    zakres_pionowy,
    znajdz_pas_legendy,
)

# Odcinek Wyl101-D155 z dokumentacji: strona 6 arkusza, 20,5 m, Ø500, 0,3%.
STRONA_Z_PROFILEM = 3
X_OD, X_DO = 4775.3, 4843.1


@pytest.fixture(scope="module")
def plik_profili(request):
    from app import create_app

    aplikacja = create_app()
    sciezka = Path(aplikacja.config["DOCS_DIR"]) / aplikacja.config["PROFILE_PDF"]
    if not sciezka.exists():
        pytest.skip(f"Brak pliku {sciezka}")
    return sciezka


@pytest.fixture(scope="module")
def strona(plik_profili):
    doc = fitz.open(plik_profili)
    yield doc[STRONA_Z_PROFILEM - 1]
    doc.close()


def test_pas_legendy_znaleziony(strona):
    """Podpisy pasm stoja przy lewej krawedzi - szukamy ich po tresci."""
    pas = znajdz_pas_legendy(strona)
    assert pas is not None
    assert pas.width > 100, "pas legendy powinien miescic 'ZAGŁĘBIENIE DNA KANAŁU'"
    assert pas.x0 < strona.rect.width * 0.1, "legenda jest przy lewej krawedzi arkusza"


def test_przyciecie_pionowe_ucina_pusty_papier(strona):
    gora, dol = zakres_pionowy(strona, X_OD, X_DO)
    assert dol > gora
    assert (dol - gora) < strona.rect.height * 0.75, (
        "bez przyciecia rysunek robi sie nieczytelnie maly"
    )


def test_wycinek_jest_poprawnym_pdf(plik_profili):
    w = wytnij(plik_profili, STRONA_Z_PROFILEM, X_OD, X_DO)
    assert w.pdf.startswith(b"%PDF")
    assert w.z_legenda is True
    assert w.szerokosc_pt > 0 and w.wysokosc_pt > 0

    doc = fitz.open(stream=w.pdf, filetype="pdf")
    try:
        assert doc.page_count == 1
        # Kopiujemy wektor, nie obrazek - to warunek ostrosci przy powiekszeniu
        # i sensownego wydruku.
        assert doc[0].get_drawings(), "wycinek powinien zawierac grafike wektorowa"
    finally:
        doc.close()


def test_wycinek_bez_legendy_jest_wezszy(plik_profili):
    z_legenda = wytnij(plik_profili, STRONA_Z_PROFILEM, X_OD, X_DO, z_legenda=True)
    bez = wytnij(plik_profili, STRONA_Z_PROFILEM, X_OD, X_DO, z_legenda=False)
    assert bez.szerokosc_pt < z_legenda.szerokosc_pt
    assert bez.z_legenda is False


def test_profil_o_zerowym_obrysie_dostaje_minimalna_szerokosc(plik_profili):
    """Cztery profile maja x_od == x_do - bez tego wyszedlby pusty obrazek."""
    w = wytnij(plik_profili, STRONA_Z_PROFILEM, 3000.0, 3000.0, z_legenda=False)
    assert w.x_do - w.x_od >= MIN_SZEROKOSC_PT - 0.01


def test_png_powstaje_z_pdf(plik_profili):
    w = wytnij(plik_profili, STRONA_Z_PROFILEM, X_OD, X_DO)
    obraz = w.png(dpi=100)
    assert obraz.startswith(b"\x89PNG")
    assert len(obraz) > 5000


def test_zla_strona_konczy_sie_bledem(plik_profili):
    with pytest.raises(ValueError, match="nie ma strony"):
        wytnij(plik_profili, 999, X_OD, X_DO)


def test_klucz_cache_rozroznia_warianty():
    podstawa = klucz_cache(3, 100.0, 200.0, True, ".png", 150)
    assert podstawa != klucz_cache(3, 100.0, 200.0, False, ".png", 150)
    assert podstawa != klucz_cache(3, 100.0, 200.0, True, ".png", 300)
    assert podstawa != klucz_cache(4, 100.0, 200.0, True, ".png", 150)
    assert podstawa == klucz_cache(3, 100.0, 200.0, True, ".png", 150)


# ------------------------------------------------------------- endpointy


def test_wycinek_profilu_przez_http(klient, db):
    from sqlalchemy import select

    from app.models import Profile

    profil = db.session.scalar(
        select(Profile).where(Profile.bbox.isnot(None), Profile.sheet_id.isnot(None))
    )
    if profil is None:
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    png = klient.get(f"/profil/{profil.id}/wycinek.png")
    assert png.status_code == 200
    assert png.mimetype == "image/png"

    pdf = klient.get(f"/profil/{profil.id}/wycinek.pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")


def test_wycinek_odcinka_przez_http(klient, db):
    from sqlalchemy import func, select

    from app.models import Segment

    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    odpowiedz = klient.get("/odcinek/Wyl101/D155/wycinek.png")
    assert odpowiedz.status_code == 200
    assert odpowiedz.mimetype == "image/png"


def test_wycinek_nieistniejacego_odcinka_to_404(klient):
    assert klient.get("/odcinek/XXX1/XXX2/wycinek.png").status_code == 404


def test_strona_profilu_nie_renderuje_wycinka_z_gory(klient, db):
    """Konwersja PDF ma ruszac dopiero na zadanie.

    Na stronie ma byc przycisk i adres, ale zaden <img src> wskazujacy
    na wycinek - inaczej przegladarka pobralaby go od razu.
    """
    from sqlalchemy import select

    from app.models import Profile

    profil = db.session.scalar(select(Profile).where(Profile.sheet_id.isnot(None)))
    if profil is None:
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    tresc = klient.get(f"/profil/{profil.id}").get_data(as_text=True)
    assert "Pokaż wycinek z oryginału" in tresc
    assert f'src="/profil/{profil.id}/wycinek.png' not in tresc
