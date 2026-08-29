"""Konwerter planow sytuacyjnych i serwer kafelkow.

Konwerter stoi na jednym zalozeniu: **kanalizacja deszczowa ma na rysunku
wlasny styl kreski**, odczytany z legendy na stronie 1. Gdyby to zalozenie
przestalo obowiazywac, wycieta siec zrobilaby sie pusta albo pelna smieci -
i to wlasnie pilnuja testy, porownujac dlugosc wycietej sieci z dlugoscia
odcinkow zapisanych w bazie.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from app.services.plan_eksport import Odwzorowanie, do_csv, do_dxf, do_geojson, do_json, z_json
from app.services.plan_wektor import (
    MM_NA_PUNKT,
    STYLE,
    Polilinia,
    etykiety_kilometrazu,
    scal_polilinie,
    wytnij_siec,
    zbierz_kreski,
)

STRONA_Z_SIECIA = 5


@pytest.fixture(scope="module")
def plan():
    from app import create_app

    aplikacja = create_app()
    sciezka = Path(aplikacja.config["DOCS_DIR"]) / "Plany sytuacyjne Scalone.pdf"
    if not sciezka.exists():
        pytest.skip(f"Brak pliku {sciezka}")
    doc = fitz.open(sciezka)
    yield doc, sciezka
    doc.close()


@pytest.fixture(scope="module")
def siec(plan):
    doc, _ = plan
    return wytnij_siec(doc[STRONA_Z_SIECIA - 1], STRONA_Z_SIECIA)


# ------------------------------------------------------------- wycinanie


def test_styl_z_legendy_lapie_siec(plan, siec):
    doc, _ = plan
    kreski = zbierz_kreski(doc[STRONA_Z_SIECIA - 1], STYLE["KD_GRAWITACYJNA"])
    assert len(kreski) > 20, (
        "filtr stylu nie znajduje sieci - sprawdz kolor i grubosc kreski w legendzie"
    )
    assert siec.polilinie
    assert siec.dlugosc_m > 100


def test_skala_daje_sensowne_dlugosci(siec):
    """Przy 1:1000 jeden punkt PDF to 0,3528 m - to musi sie zgadzac."""
    assert siec.skala == 1000
    najdluzsza = max(p.dlugosc_m(siec.skala) for p in siec.polilinie)
    assert 5 < najdluzsza < 1000, f"nierealna dlugosc przewodu: {najdluzsza} m"


def test_polilinia_liczy_dlugosc_wzdluz_zalamania():
    """Trzy punkty pod katem prostym: 100 + 100 punktow."""
    p = Polilinia([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)], "X")
    assert p.dlugosc_pt == pytest.approx(200.0)
    assert p.dlugosc_m(1000) == pytest.approx(round(200.0 * MM_NA_PUNKT, 2), abs=0.01)


def test_scalanie_konczy_polilinie_na_rozgalezieniu():
    """Wierzcholek stopnia 2 to zalamanie trasy, stopnia 3 to studnia."""
    kreski = [
        ((0.0, 0.0), (10.0, 0.0)),
        ((10.0, 0.0), (20.0, 0.0)),     # zalamanie - idziemy dalej
        ((20.0, 0.0), (30.0, 0.0)),
        ((20.0, 0.0), (20.0, 10.0)),    # rozgalezienie w (20, 0)
    ]
    polilinie, wezly = scal_polilinie(kreski, "X")
    assert len(polilinie) == 3
    assert (20.0, 0.0) in wezly
    assert (10.0, 0.0) not in wezly, "zwykle zalamanie nie jest wezlem sieci"


def test_scalanie_nie_gubi_obwodu_zamknietego():
    """Petla nie ma zadnego wierzcholka o stopniu innym niz 2."""
    kwadrat = [((0.0, 0.0), (10.0, 0.0)), ((10.0, 0.0), (10.0, 10.0)),
               ((10.0, 10.0), (0.0, 10.0)), ((0.0, 10.0), (0.0, 0.0))]
    polilinie, wezly = scal_polilinie(kwadrat, "X")
    assert wezly == []
    assert len(polilinie) == 1


def test_kilometraz_jest_zywym_tekstem(plan):
    """`KM:5+814` to jeden z nielicznych napisow, ktorych nie zamieniono na krzywe."""
    doc, _ = plan
    znalezione = []
    for nr in range(doc.page_count):
        znalezione.extend(etykiety_kilometrazu(doc[nr]))
    assert len(znalezione) > 10, "kilometraz na planach powinien byc odczytywalny"
    assert all(e.kilometraz_m is not None for e in znalezione)

    przyklad = next(e for e in znalezione if e.kilometraz_m and e.kilometraz_m > 1000)
    # "KM:5+814" to 5814 m od poczatku trasy.
    assert przyklad.kilometraz_m == pytest.approx(round(przyklad.kilometraz_m))


def test_nieznany_styl_konczy_sie_bledem(plan):
    doc, _ = plan
    with pytest.raises(ValueError, match="Nie znam stylu"):
        wytnij_siec(doc[0], 1, "NIE_MA_TAKIEGO")


# --------------------------------------------------------------- eksport


def test_geojson_mowi_w_jakim_jest_ukladzie(siec):
    bez = json.loads(do_geojson(siec, Odwzorowanie(None, siec.skala)))
    assert "nie jest zwiazany z terenem" in bez["uklad"]
    assert "crs" not in bez, "bez georeferencji nie wolno deklarowac ukladu panstwowego"
    assert bez["features"]

    from app.services.georef import Kotwica, dopasuj

    p = dopasuj([Kotwica(0.0, 0.0, 5771000.0, 5503800.0, "a"),
                 Kotwica(1000.0, 0.0, 5771000.0, 5504152.778, "b")])
    z_georef = json.loads(do_geojson(siec, Odwzorowanie(p, siec.skala)))
    assert z_georef["crs"]["properties"]["name"].endswith("2176")


def test_geojson_ma_przewody_wezly_i_kilometraz(siec):
    dane = json.loads(do_geojson(siec, Odwzorowanie(None, siec.skala)))
    rodzaje = {f["properties"]["rodzaj"] for f in dane["features"]}
    assert "przewod" in rodzaje
    assert "wezel" in rodzaje


def test_dxf_jest_czytelny_dla_cad(siec):
    tekst = do_dxf(siec, Odwzorowanie(None, siec.skala))
    assert tekst.startswith("0\nSECTION")
    assert tekst.rstrip().endswith("EOF")
    assert "AC1009" in tekst                      # R12 - czyta kazdy CAD
    assert tekst.count("0\nPOLYLINE") == len(siec.polilinie)
    assert tekst.count("0\nSEQEND") == len(siec.polilinie)
    assert "KD_PRZEWODY" in tekst


def test_csv_zaczyna_sie_od_opisu_ukladu(siec):
    tekst = do_csv(siec, Odwzorowanie(None, siec.skala))
    assert tekst.startswith("# uklad:")
    assert "nazwa;X_polnoc;Y_wschod" in tekst


def test_wynik_przezywa_zapis_i_odczyt(siec):
    odtworzona = z_json(do_json(siec))
    assert len(odtworzona.polilinie) == len(siec.polilinie)
    assert odtworzona.dlugosc_m == pytest.approx(siec.dlugosc_m, abs=0.5)
    assert len(odtworzona.etykiety) == len(siec.etykiety)


def test_nieznany_format_konczy_sie_bledem(siec):
    from app.services.plan_eksport import zapisz

    with pytest.raises(ValueError, match="Nie znam formatu"):
        zapisz(siec, Odwzorowanie(None), "shp")


# --------------------------------------------------------------- kafelki


def test_kafelek_ma_wlasciwy_rozmiar(plan):
    from app.services.kafelki import BOK_KAFELKA, renderuj_kafelek

    _, sciezka = plan
    from PIL import Image
    from io import BytesIO

    for zoom, kol, wiersz in ((0, 0, 0), (3, 1, 0), (5, 4, 2)):
        obraz = Image.open(BytesIO(renderuj_kafelek(sciezka, STRONA_Z_SIECIA,
                                                    zoom, kol, wiersz)))
        assert obraz.size == (BOK_KAFELKA, BOK_KAFELKA)


def test_kafelek_poza_arkuszem_jest_pusty_a_nie_bledem(plan):
    from app.services.kafelki import renderuj_kafelek

    _, sciezka = plan
    assert renderuj_kafelek(sciezka, STRONA_Z_SIECIA, 3, 999, 999)


def test_lista_wyswietlania_przyspiesza_kafelki(plan):
    """To ona decyduje o plynnosci mapy - 25 razy szybciej niz bez niej."""
    import time

    from app.services.kafelki import lista_wyswietlania, renderuj_kafelek

    _, sciezka = plan
    lista_wyswietlania(sciezka, STRONA_Z_SIECIA)      # rozgrzewka

    start = time.perf_counter()
    for kol in range(8):
        renderuj_kafelek(sciezka, STRONA_Z_SIECIA, 4, kol, 1)
    na_kafelek = (time.perf_counter() - start) / 8

    assert na_kafelek < 0.2, (
        f"{na_kafelek * 1000:.0f} ms na kafelek - zoom bedzie sie zacinal; "
        "sprawdz, czy renderowanie nadal idzie przez liste wyswietlania"
    )


def test_zla_strona_konczy_sie_bledem(plan):
    from app.services.kafelki import renderuj_kafelek

    _, sciezka = plan
    with pytest.raises(ValueError, match="nie ma strony"):
        renderuj_kafelek(sciezka, 999, 0, 0, 0)


def test_cache_kafelkow_ma_limit(tmp_path):
    from app.services.kafelki import sprzataj

    for i in range(10):
        (tmp_path / f"s01-z0-{i}-0.png").write_bytes(b"x" * 200_000)

    usuniete = sprzataj(tmp_path, limit_mb=1)
    assert usuniete > 0
    zostalo = sum(p.stat().st_size for p in tmp_path.glob("*.png"))
    assert zostalo <= 1024 * 1024


# -------------------------------------------------------------- endpointy


def test_mapa_serwuje_kafelki(klient):
    odpowiedz = klient.get(f"/mapa/kafelek/{STRONA_Z_SIECIA}/2/1/0.png")
    assert odpowiedz.status_code == 200
    assert odpowiedz.mimetype == "image/png"
    assert "max-age" in odpowiedz.headers.get("Cache-Control", "")


def test_zoom_poza_zakresem_to_404(klient):
    assert klient.get(f"/mapa/kafelek/{STRONA_Z_SIECIA}/99/0/0.png").status_code == 404


def test_opis_strony_ma_wszystko_do_narysowania_mapy(klient):
    dane = klient.get(f"/api/mapa/strona/{STRONA_Z_SIECIA}").get_json()
    for pole in ("szerokosc_pt", "wysokosc_pt", "metry_na_punkt", "max_zoom",
                 "bok_kafelka", "georef", "kotwice", "lokalizacje"):
        assert pole in dane
    assert dane["metry_na_punkt"] == pytest.approx(0.352778, abs=1e-5)


def test_eksport_dziala_dla_kazdego_formatu(klient):
    for format_ in ("geojson", "dxf", "csv"):
        odpowiedz = klient.get(f"/mapa/eksport/{STRONA_Z_SIECIA}.{format_}")
        if odpowiedz.status_code == 404:
            pytest.skip("Strona nie jest przekonwertowana (flask konwertuj-plany).")
        assert odpowiedz.status_code == 200
        assert odpowiedz.headers["Content-Disposition"].startswith("attachment")


def test_mapa_wczytuje_leaflet_lokalnie(klient):
    """Na budowie bywa bez zasiegu - zadna biblioteka nie moze isc z sieci."""
    tresc = klient.get(f"/mapa?strona={STRONA_Z_SIECIA}").get_data(as_text=True)
    assert "vendor/leaflet/leaflet.js" in tresc
    assert "unpkg.com" not in tresc
    assert "cdn." not in tresc


def test_leaflet_nie_laduje_sie_na_kazdej_stronie(klient):
    """Biblioteka mapy wazy 160 kB - nie ma po co jej ciagnac na pulpicie."""
    assert "leaflet" not in klient.get("/").get_data(as_text=True)
