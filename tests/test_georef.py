"""Zwiazanie arkusza planu z ukladem PL-2000/5.

Testy odtwarzaja sytuacje z budowy: bierzemy znany arkusz, udajemy, ze ktos
wskazal na nim punkty o znanych wspolrzednych, i sprawdzamy, czy program
odzyskuje **skale i obrot rysunku**. To jedyny sprawdzian, ktory ma sens -
same wspolczynniki nic nie mowia, a odchylka przy dwoch kotwicach jest zawsze
zerowa z definicji.
"""
from __future__ import annotations

import math

import pytest

from app.services.georef import (
    METRY_NA_PUNKT_1_1000,
    Kotwica,
    dopasuj,
    odleglosc_m,
    plik_swiata,
    z_wspolczynnikow,
)

# Prawdziwy poczatek ukladu w okolicy budowy - z pliku osnowy DK29.
X0, Y0 = 5771000.0, 5503800.0


def arkusz(obrot_stopni: float = 7.0, skala: float = METRY_NA_PUNKT_1_1000):
    """Zwraca funkcje punkt rysunku -> wspolrzedne terenowe."""
    kat = math.radians(obrot_stopni)

    def przelicz(x_pt: float, y_pt: float) -> tuple[float, float]:
        u, v = x_pt, -y_pt          # os Y w PDF rosnie w dol
        polnoc = X0 + skala * (math.sin(kat) * u + math.cos(kat) * v)
        wschod = Y0 + skala * (math.cos(kat) * u - math.sin(kat) * v)
        return polnoc, wschod

    return przelicz


def kotwice_z(punkty, przelicz):
    return [Kotwica(x, y, *przelicz(x, y), nazwa=f"o{i}")
            for i, (x, y) in enumerate(punkty, 1)]


PUNKTY = [(300.0, 400.0), (2800.0, 900.0), (1500.0, 1400.0)]


# ------------------------------------------------------------ dopasowanie


def test_dwie_kotwice_odzyskuja_skale_i_obrot():
    p = dopasuj(kotwice_z(PUNKTY[:2], arkusz(7.0)))
    assert p.skala_rysunku == 1000
    assert p.obrot_stopnie == pytest.approx(7.0, abs=1e-6)
    assert p.wiarygodne


def test_jedna_kotwica_to_za_malo():
    with pytest.raises(ValueError, match="co najmniej"):
        dopasuj(kotwice_z(PUNKTY[:1], arkusz()))


def test_dwie_kotwice_w_tym_samym_miejscu():
    przelicz = arkusz()
    ten_sam = [(500.0, 500.0), (500.0, 500.0)]
    with pytest.raises(ValueError, match="tym samym miejscu"):
        dopasuj(kotwice_z(ten_sam, przelicz))


def test_przeliczenie_dziala_w_obie_strony():
    p = dopasuj(kotwice_z(PUNKTY, arkusz(12.5)))
    polnoc, wschod = p.na_teren(1234.0, 567.0)
    assert p.na_rysunek(polnoc, wschod) == pytest.approx((1234.0, 567.0), abs=0.01)


def test_trzecia_kotwica_potwierdza_dopasowanie():
    """Dwie kotwice pasuja idealnie zawsze - dopiero trzecia jest sprawdzianem."""
    przelicz = arkusz(7.0)
    z_dwoch = dopasuj(kotwice_z(PUNKTY[:2], przelicz))
    assert z_dwoch.rmse_m == pytest.approx(0.0, abs=1e-6)

    sprawdzana = PUNKTY[2]
    oczekiwane = przelicz(*sprawdzana)
    policzone = z_dwoch.na_teren(*sprawdzana)
    assert odleglosc_m(oczekiwane, policzone) < 0.01


def test_pomylona_kotwica_wychodzi_na_zlej_skali():
    """Wskazanie nie tego repera psuje skale - i to widac natychmiast."""
    przelicz = arkusz(7.0)
    dobre = kotwice_z(PUNKTY[:2], przelicz)
    zla = Kotwica(dobre[1].x_pt, dobre[1].y_pt,
                  dobre[1].x_gis + 400.0, dobre[1].y_gis - 300.0, "pomylka")

    p = dopasuj([dobre[0], zla])
    assert not p.wiarygodne
    assert p.skala_rysunku != 1000


def test_trzecia_kotwica_ujawnia_blad_dwoch_pozostalych():
    """Przy trzech kotwicach zla wskazanie podnosi odchylke."""
    przelicz = arkusz(7.0)
    dobre = kotwice_z(PUNKTY, przelicz)
    dobre[2] = Kotwica(dobre[2].x_pt, dobre[2].y_pt,
                       dobre[2].x_gis + 5.0, dobre[2].y_gis, dobre[2].nazwa)

    p = dopasuj(dobre)
    assert p.rmse_m > 1.0
    assert not p.wiarygodne


def test_wspolczynniki_przezywaja_zapis_i_odczyt():
    p = dopasuj(kotwice_z(PUNKTY, arkusz(3.25)))
    odtworzony = z_wspolczynnikow(p.to_dict()["wspolczynniki"])
    assert odtworzony.na_teren(900.0, 250.0) == p.na_teren(900.0, 250.0)
    assert odtworzony.skala_rysunku == p.skala_rysunku


def test_plik_swiata_ma_szesc_wierszy():
    p = dopasuj(kotwice_z(PUNKTY, arkusz(0.0)))
    wiersze = plik_swiata(p, dpi=150).strip().splitlines()
    assert len(wiersze) == 6
    # Przy zerowym obrocie rozmiar piksela w obu osiach musi byc ten sam
    # co do znaku odwrotny: polnoc maleje w dol obrazu.
    a, d, b, e = (float(w) for w in wiersze[:4])
    assert a == pytest.approx(-e, rel=1e-9)
    assert b == pytest.approx(0.0, abs=1e-9)
    assert d == pytest.approx(0.0, abs=1e-9)


# -------------------------------------------------------------- endpointy


@pytest.fixture()
def arkusz_planu(klient, db):
    from sqlalchemy import select

    from app.models import PlanAnchor, PlanGeoref, PlanSheet

    strona = db.session.scalar(select(PlanSheet).order_by(PlanSheet.nr_strony))
    if strona is None:
        pytest.skip("Brak zarejestrowanych stron planu.")

    # Testy nie moga zostawic po sobie zwiazania arkusza.
    for kotwica in list(strona.kotwice):
        db.session.delete(kotwica)
    if strona.georef is not None:
        db.session.delete(strona.georef)
    db.session.commit()

    yield strona

    db.session.execute(
        PlanAnchor.__table__.delete().where(PlanAnchor.strona_id == strona.id))
    db.session.execute(
        PlanGeoref.__table__.delete().where(PlanGeoref.strona_id == strona.id))
    db.session.commit()


def test_georeferencja_przez_api(klient, arkusz_planu):
    przelicz = arkusz(4.0)
    odpowiedzi = []
    for nazwa, (x, y) in zip(("kontrola-a", "kontrola-b"), PUNKTY[:2]):
        polnoc, wschod = przelicz(x, y)
        odpowiedzi.append(klient.post("/api/mapa/kotwica", json={
            "strona_id": arkusz_planu.id, "x_pt": x, "y_pt": y,
            "nazwa": nazwa, "x_gis": polnoc, "y_gis": wschod,
        }))

    assert odpowiedzi[0].status_code == 200
    assert odpowiedzi[0].get_json()["georef"] is None, "jedna kotwica to za malo"

    dane = odpowiedzi[1].get_json()
    assert dane["georef"]["skala_rysunku"] == 1000
    assert dane["georef"]["wiarygodne"] is True

    # Po zwiazaniu klikniecie w mape podaje wspolrzedne terenowe.
    x, y = PUNKTY[2]
    wynik = klient.get(f"/api/mapa/wspolrzedne/{arkusz_planu.nr_strony}",
                       query_string={"x_pt": x, "y_pt": y}).get_json()
    oczekiwane = przelicz(x, y)
    assert odleglosc_m(oczekiwane, (wynik["x_gis"], wynik["y_gis"])) < 0.05


def test_repery_pojawiaja_sie_na_planie_po_zwiazaniu(klient, arkusz_planu, db):
    """To jest wlasciwy powod robienia georeferencji.

    Do tej pory "najblizsze repery" nie mogly zadzialac, bo repery nie mialy
    jak trafic na plan - tabela pozycji wskazuje wylacznie na obiekty sieci.
    """
    from sqlalchemy import select

    from app.models import SurveyPoint

    przed = klient.get(f"/api/mapa/repery/{arkusz_planu.nr_strony}").get_json()
    assert przed["dostepne"] is False

    # Kotwiczymy arkusz na dwoch prawdziwych reperach z osnowy, umieszczajac je
    # w miejscach rysunku odleglych o tyle, ile wynosi ich odleglosc w terenie.
    punkty = list(db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.x.isnot(None)).limit(2)))
    if len(punkty) < 2:
        pytest.skip("Osnowa nie jest wczytana.")

    odleglosc = odleglosc_m((float(punkty[0].x), float(punkty[0].y)),
                            (float(punkty[1].x), float(punkty[1].y)))
    rozstaw_pt = odleglosc / METRY_NA_PUNKT_1_1000

    for punkt, (x, y) in zip(punkty, [(200.0, 300.0), (200.0 + rozstaw_pt, 300.0)]):
        odpowiedz = klient.post("/api/mapa/kotwica", json={
            "strona_id": arkusz_planu.id, "x_pt": x, "y_pt": y, "reper": punkt.nazwa,
        })
        assert odpowiedz.status_code == 200

    po = klient.get(f"/api/mapa/repery/{arkusz_planu.nr_strony}").get_json()
    assert po["dostepne"] is True
    nazwy = {r["nazwa"] for r in po["repery"]}
    assert {p.nazwa for p in punkty} <= nazwy, "wskazane repery musza byc na liscie"


def test_kotwica_z_nieznanym_reperem_prosi_o_wspolrzedne(klient, arkusz_planu):
    odpowiedz = klient.post("/api/mapa/kotwica", json={
        "strona_id": arkusz_planu.id, "x_pt": 10.0, "y_pt": 10.0, "reper": "nie-ma-takiego",
    })
    assert odpowiedz.status_code == 400
    assert "nie-ma-takiego" in odpowiedz.get_json()["blad"]


def test_bez_georeferencji_plik_swiata_jest_niedostepny(klient, arkusz_planu):
    odpowiedz = klient.get(f"/mapa/eksport/{arkusz_planu.nr_strony}.pgw")
    assert odpowiedz.status_code == 404
