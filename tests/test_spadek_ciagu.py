"""Testy tyczenia ciagu rur - to, co widzi osoba przy niwelatorze."""
import pytest

from app.services.spadek_ciagu import (
    TRYB_OS,
    TRYB_SCIANA,
    PunktTyczenia,
    podpowiedz_karb_m,
    policz_odcinek,
    promien_konca,
)


class FakeObiekt:
    def __init__(self, kod, typ, srednica=None):
        self.kod, self.typ, self.srednica_studni_mm = kod, typ, srednica


class FakeSegment:
    def __init__(self, od, do, dlugosc, dn, rz_od, rz_do, spadek=None):
        self.obiekt_od, self.obiekt_do = od, do
        self.dlugosc_m, self.dn_mm = dlugosc, dn
        self.rzedna_dna_od, self.rzedna_dna_do = rz_od, rz_do
        self.spadek_promile = spadek

    @property
    def nazwa(self):
        return f"{self.obiekt_od.kod}-{self.obiekt_do.kod}"


@pytest.fixture()
def studnie():
    from app.models import TypObiektu

    return (
        FakeObiekt("D114", TypObiektu.STUDNIA, 1500),
        FakeObiekt("D115", TypObiektu.STUDNIA, 1500),
    )


# ------------------------------------------------- odejmowanie srednic studni


def test_promien_studni_to_polowa_srednicy(studnie):
    assert promien_konca(studnie[0]) == pytest.approx(0.75)


def test_wpust_i_wylot_nie_maja_czego_odjac():
    from app.models import TypObiektu

    assert promien_konca(FakeObiekt("Wp65", TypObiektu.WPUST, 500)) == 0.0
    assert promien_konca(FakeObiekt("Wyl101", TypObiektu.WYLOT)) == 0.0
    assert promien_konca(None) == 0.0


def test_reczne_nadpisanie_srednicy_ma_pierwszenstwo(studnie):
    """Monter moze podac wymiar zmierzony na budowie."""
    assert promien_konca(studnie[0], nadpisanie_mm=2000) == pytest.approx(1.0)


def test_dlugosc_rury_jest_krotsza_o_promienie_studni(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, rzedna_startowa=44.28, h_karb_m=0.5, hi=46.782)
    assert w.dlugosc_osiowa_m == 50.5
    assert w.dlugosc_rury_m == pytest.approx(49.0)


# --------------------------------------------------------------- dwa tryby


def test_tryb_sciana_daje_spadek_stromszy(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, rzedna_startowa=44.28, h_karb_m=0.5, hi=46.782)
    assert w.spadek_sciana_promile == pytest.approx(10.204, abs=0.01)
    assert w.spadek_os_promile == pytest.approx(9.901, abs=0.01)
    assert w.spadek_sciana_promile > w.spadek_os_promile


def test_tryb_zmienia_rzedna_koncowa(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    sciana = policz_odcinek(seg, 44.28, 0.5, 46.782, tryb=TRYB_SCIANA)
    osiowy = policz_odcinek(seg, 44.28, 0.5, 46.782, tryb=TRYB_OS)
    # Ten sam odcinek rury, stromszy spadek -> nizszy koniec.
    assert sciana.rzedna_koniec < osiowy.rzedna_koniec
    assert sciana.rzedna_koniec == pytest.approx(43.78, abs=1e-3)


# ------------------------------------------------------- odczyt na lacie


def test_odczyt_uwzglednia_wysokosc_karba(studnie):
    """Lata stoi na karbie, nie na cieku - odczyt musi to uwzgledniac."""
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    bez = policz_odcinek(seg, 44.28, 0.0, 46.782)
    z_karbem = policz_odcinek(seg, 44.28, 0.5, 46.782)
    assert bez.punkty[0].odczyt - z_karbem.punkty[0].odczyt == pytest.approx(0.5, abs=1e-6)


def test_odczyt_na_starcie_zgadza_sie_z_hi(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, rzedna_startowa=44.28, h_karb_m=0.5, hi=46.782)
    p = w.punkty[0]
    assert p.rzedna_dna == pytest.approx(44.28)
    assert p.rzedna_laty == pytest.approx(44.78)
    assert p.odczyt == pytest.approx(46.782 - 44.78, abs=1e-3)


def test_odczyt_rosnie_wzdluz_spadku(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, 44.28, 0.5, 46.782, krok_m=6.0)
    odczyty = [p.odczyt for p in w.punkty]
    assert odczyty == sorted(odczyty), "kanal opada, wiec odczyt musi rosnac"
    assert w.punkty[-1].odczyt - w.punkty[0].odczyt == pytest.approx(0.5, abs=0.01)


def test_krok_wyznacza_punkty_i_zawsze_konczy_na_koncu(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, 44.28, 0.5, 46.782, krok_m=6.0)
    assert w.punkty[0].odleglosc_m == 0.0
    assert w.punkty[-1].odleglosc_m == pytest.approx(49.0)
    assert "początek" in w.punkty[0].opis and "koniec" in w.punkty[-1].opis


def test_odczyt_poza_lata_jest_oznaczony(studnie):
    """Reper 40 m nad rura - fizycznie nie da sie zmierzyc."""
    seg = FakeSegment(studnie[0], studnie[1], 50.5, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, 44.28, 0.5, 86.632)
    assert all(not p.wykonalny for p in w.punkty)
    assert any("poza łatą" in u for u in w.uwagi)


# -------------------------------------------------------------- braki danych


def test_brak_rzednych_liczy_ze_spadku(studnie):
    seg = FakeSegment(studnie[0], studnie[1], 50.0, 500, None, None, 10.0)
    w = policz_odcinek(seg, 44.28, 0.5, 46.782)
    assert w.roznica_rzednych_m == pytest.approx(0.5)
    assert any("spadku projektowego" in u for u in w.uwagi)


def test_brak_dlugosci_daje_uwage(studnie):
    seg = FakeSegment(studnie[0], studnie[1], None, 500, 44.28, 43.78, 10.0)
    w = policz_odcinek(seg, 44.28, 0.5, 46.782)
    assert any("długości" in u for u in w.uwagi)


# --------------------------------------------------------- podpowiedz karba


def test_podpowiedz_karba_bierze_srednice_zewnetrzna():
    assert podpowiedz_karb_m(500) == pytest.approx(0.5)
    assert podpowiedz_karb_m(600) == pytest.approx(0.63)   # OD630
    assert podpowiedz_karb_m(300) == pytest.approx(0.315)  # OD315
    assert podpowiedz_karb_m(None) is None


# ------------------------------------------------------------------- HTTP


def test_endpoint_ciagu_liczy_odcinek(klient):
    d = klient.post("/niwelator/ciag-rur/oblicz", json={
        "od": "D114", "do": "D115",
        "rzedna_repera": 45.350, "odczyt_wstecz": 1.432,
        "h_karb": 0.5, "tryb": "SCIANA", "krok": "6",
    }).get_json()
    assert d["hi"] == pytest.approx(46.782, abs=1e-3)
    assert d["dlugosc_osiowa_m"] == pytest.approx(50.5)
    assert d["dlugosc_rury_m"] == pytest.approx(49.0)
    assert d["spadek_calkowity_m"] == pytest.approx(0.5, abs=0.01)
    punkty = d["odcinki"][0]["punkty"]
    assert punkty[0]["odczyt"] == pytest.approx(2.002, abs=1e-3)
    assert all(p["wykonalny"] for p in punkty)


def test_endpoint_wymaga_obiektu_poczatkowego(klient):
    assert klient.post("/niwelator/ciag-rur/oblicz", json={}).status_code == 400


def test_endpoint_nieznany_ciag(klient):
    r = klient.post("/niwelator/ciag-rur/oblicz",
                    json={"od": "NIE_MA", "hi": 50.0, "h_karb": 0.5})
    assert r.status_code == 404


def test_strona_kalkulatora_sie_renderuje(klient):
    html = klient.get("/niwelator/ciag-rur").get_data(as_text=True)
    assert "górnym karbie" in html
    assert "ściany studni" in html
