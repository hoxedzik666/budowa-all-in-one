"""Pozycja z telefonu na planie.

Transformacja geodezyjna to jedyne miejsce w projekcie, gdzie blad w szostym
miejscu po przecinku daje kilkanascie metrow w terenie i nie widac go inaczej
niz przez porownanie z punktem kontrolnym. Na szczescie punktow kontrolnych
mamy 151 - cala osnowa DK29 ma znane wspolrzedne PL-2000.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.models import PlanAnchor, PlanGeoref, PlanSheet, SurveyPoint
from app.services.georef import METRY_NA_PUNKT_1_1000, odleglosc_m
from tests.conftest import wymaga_pyproj
from app.services.wspolrzedne import (
    PROG_DOKLADNOSCI_M,
    gps_na_pl2000,
    pl2000_na_gps,
    sprawdz_pozycje,
)

# Krosno Odrzanskie. Cala budowa musi wyladowac w tej okolicy.
KROSNO_SZEROKOSC = (51.90, 52.20)
KROSNO_DLUGOSC = (14.90, 15.30)


# ------------------------------------------------------------ transformacja


@wymaga_pyproj
def test_osnowa_lezy_w_krosnie_odrzanskim(db):
    """Najmocniejszy sprawdzian, jaki mamy: 151 punktow o znanych wspolrzednych.

    Zla definicja ukladu albo zamienione osie wyrzucilyby te punkty setki
    kilometrow dalej - i widac to natychmiast.
    """
    punkty = list(db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.x.isnot(None), SurveyPoint.y.isnot(None))))
    if len(punkty) < 10:
        pytest.skip("Osnowa nie jest wczytana.")

    for punkt in punkty:
        szerokosc, dlugosc = pl2000_na_gps(float(punkt.x), float(punkt.y))
        assert KROSNO_SZEROKOSC[0] <= szerokosc <= KROSNO_SZEROKOSC[1], (
            f"{punkt.nazwa}: szerokość {szerokosc} poza okolicą Krosna")
        assert KROSNO_DLUGOSC[0] <= dlugosc <= KROSNO_DLUGOSC[1], (
            f"{punkt.nazwa}: długość {dlugosc} poza okolicą Krosna")


@wymaga_pyproj
def test_przeliczenie_tam_i_z_powrotem(db):
    punkt = db.session.scalar(select(SurveyPoint).where(SurveyPoint.x.isnot(None)))
    if punkt is None:
        pytest.skip("Osnowa nie jest wczytana.")

    polnoc, wschod = float(punkt.x), float(punkt.y)
    szerokosc, dlugosc = pl2000_na_gps(polnoc, wschod)
    wrocone = gps_na_pl2000(szerokosc, dlugosc)

    # Milimetry. Wiecej znaczyloby, ze cos jest nie tak z definicja ukladu.
    assert odleglosc_m((polnoc, wschod), wrocone) < 0.01


@wymaga_pyproj
def test_osie_nie_sa_zamienione(db):
    """W PL-2000 X to polnoc, Y to wschod - odwrotnie niz w matematyce.

    Zamiana tych dwoch to najczestszy blad przy pracy z ukladami polskimi
    i najlatwiejszy do przeoczenia, bo obie liczby zaczynaja sie od piatki.
    """
    polnoc, wschod = gps_na_pl2000(52.05, 15.09)
    assert 5_700_000 < polnoc < 5_800_000, f"X (północ) wyszło {polnoc}"
    assert 5_450_000 < wschod < 5_560_000, f"Y (wschód) wyszło {wschod}"


@wymaga_pyproj
def test_ruch_na_polnoc_zwieksza_wspolrzedna_polnocna():
    poludniej = gps_na_pl2000(52.00, 15.09)
    polnocniej = gps_na_pl2000(52.01, 15.09)
    assert polnocniej[0] > poludniej[0]
    # 0,01 stopnia szerokosci to ok. 1,11 km.
    assert 1050 < polnocniej[0] - poludniej[0] < 1170


# ------------------------------------------------------------- ostrzezenia


def test_pozycja_spoza_polski_jest_wylapywana():
    uwaga = sprawdz_pozycje(37.7749, -122.4194)      # San Francisco
    assert uwaga is not None
    assert "poza Polską" in uwaga


def test_slaba_dokladnosc_jest_zglaszana():
    assert sprawdz_pozycje(52.05, 15.09, dokladnosc_m=5.0) is None
    uwaga = sprawdz_pozycje(52.05, 15.09, dokladnosc_m=PROG_DOKLADNOSCI_M + 20)
    assert uwaga is not None and "Dokładność" in uwaga


# -------------------------------------------------------------- endpoint


@pytest.fixture()
def arkusz_zwiazany(klient, db):
    """Arkusz z georeferencja zalozona na dwoch prawdziwych reperach.

    Kotwice ustawiamy tak, zeby odleglosc na rysunku odpowiadala odleglosci
    w terenie - inaczej skala wyszlaby bez sensu.
    """
    strona = db.session.scalar(select(PlanSheet).order_by(PlanSheet.nr_strony))
    if strona is None:
        pytest.skip("Brak arkuszy planu.")

    punkty = list(db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.x.isnot(None)).limit(2)))
    if len(punkty) < 2:
        pytest.skip("Osnowa nie jest wczytana.")

    db.session.execute(delete(PlanAnchor).where(PlanAnchor.strona_id == strona.id))
    db.session.execute(delete(PlanGeoref).where(PlanGeoref.strona_id == strona.id))
    db.session.commit()

    odleglosc = odleglosc_m((float(punkty[0].x), float(punkty[0].y)),
                            (float(punkty[1].x), float(punkty[1].y)))
    rozstaw = odleglosc / METRY_NA_PUNKT_1_1000

    for punkt, (x, y) in zip(punkty, [(400.0, 500.0), (400.0 + rozstaw, 500.0)]):
        odpowiedz = klient.post("/api/mapa/kotwica", json={
            "strona_id": strona.id, "x_pt": x, "y_pt": y, "reper": punkt.nazwa})
        assert odpowiedz.status_code == 200

    db.session.refresh(strona)
    yield strona, punkty

    db.session.execute(delete(PlanAnchor).where(PlanAnchor.strona_id == strona.id))
    db.session.execute(delete(PlanGeoref).where(PlanGeoref.strona_id == strona.id))
    db.session.commit()


@wymaga_pyproj
def test_gps_trafia_w_reper_ktory_sam_wskazalismy(klient, arkusz_zwiazany):
    """Najlepszy sprawdzian calego lancucha GPS -> PL-2000 -> punkt rysunku.

    Bierzemy reper, ktorego pozycje na rysunku sami podalismy, przeliczamy go
    na WGS84 i pytamy serwer, gdzie ten punkt lezy. Musi wskazac to samo miejsce.
    """
    strona, punkty = arkusz_zwiazany
    reper = punkty[0]
    szerokosc, dlugosc = pl2000_na_gps(float(reper.x), float(reper.y))

    dane = klient.get(f"/api/mapa/z-gps/{strona.nr_strony}", query_string={
        "lat": szerokosc, "lon": dlugosc, "dokladnosc": 4.0}).get_json()

    assert dane["na_arkuszu"] is True
    assert dane["x_pt"] == pytest.approx(400.0, abs=0.5)
    assert dane["y_pt"] == pytest.approx(500.0, abs=0.5)
    assert dane["uwaga"] is None


@wymaga_pyproj
def test_odpowiedz_zawsze_niesie_dokladnosc(klient, arkusz_zwiazany):
    """GPS z telefonu ma 3-10 m i nikt nie moze o tym zapomniec."""
    strona, _ = arkusz_zwiazany
    dane = klient.get(f"/api/mapa/z-gps/{strona.nr_strony}", query_string={
        "lat": 52.05, "lon": 15.09, "dokladnosc": 8.0}).get_json()

    assert dane["dokladnosc_m"] == 8.0
    assert dane["promien_pt"] is not None
    assert dane["do_tyczenia"] is False


@wymaga_pyproj
def test_pozycja_daleko_od_arkusza(klient, arkusz_zwiazany):
    """Osoba po drugiej stronie Polski ma dostac wspolrzedne, ale i informacje,
    ze na tym arkuszu jej nie ma."""
    strona, _ = arkusz_zwiazany
    dane = klient.get(f"/api/mapa/z-gps/{strona.nr_strony}", query_string={
        "lat": 52.23, "lon": 21.01}).get_json()          # Warszawa
    assert dane["na_arkuszu"] is False
    assert dane["x_gis"] and dane["y_gis"]


def test_arkusz_bez_georeferencji_mowi_czego_brakuje(klient, db):
    strona = db.session.scalar(
        select(PlanSheet).where(~PlanSheet.id.in_(select(PlanGeoref.strona_id))))
    if strona is None:
        pytest.skip("Każdy arkusz ma georeferencję.")

    odpowiedz = klient.get(f"/api/mapa/z-gps/{strona.nr_strony}",
                           query_string={"lat": 52.05, "lon": 15.09})
    assert odpowiedz.status_code == 404
    dane = odpowiedz.get_json()
    assert dane["wymaga_georeferencji"] is True
    assert "repery" in dane["blad"]


def test_brak_wspolrzednych_to_400(klient, arkusz_zwiazany):
    strona, _ = arkusz_zwiazany
    assert klient.get(f"/api/mapa/z-gps/{strona.nr_strony}").status_code == 400


def test_gps_wymaga_logowania(klient_anonim):
    assert klient_anonim.get("/api/mapa/z-gps/1?lat=52&lon=15").status_code == 302
