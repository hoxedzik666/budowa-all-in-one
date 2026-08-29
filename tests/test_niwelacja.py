"""Testy obliczen niwelacyjnych - matematyka musi byc bezdyskusyjna."""
import pytest

from app.services.leveling import (
    CiagNiwelacyjny,
    Stanowisko,
    przykrycie,
    rzedna_posrednia,
    spadek_z_rzednych,
    wytycz,
)


def test_hi_to_reper_plus_odczyt_wstecz():
    st = Stanowisko(reper="o101", rzedna_repera=80.9817, odczyt_wstecz=1.432)
    assert st.hi == pytest.approx(82.4137, abs=1e-4)


def test_rzedna_punktu_z_odczytu_wprzod():
    st = Stanowisko(reper="R1", rzedna_repera=100.000, odczyt_wstecz=1.500)
    # HI = 101.500; lata pokazuje 2.300 -> punkt lezy na 99.200
    assert st.rzedna_punktu(2.300) == pytest.approx(99.200, abs=1e-4)


def test_odczyt_zadany_dla_rzednej_projektowej():
    """Najczestsza operacja brygadzisty: ile ma pokazac lata na dnie wykopu."""
    w = wytycz(rzedna_repera=85.20, odczyt_wstecz=1.432, rzedna_projektowa=84.00)
    assert w.hi == pytest.approx(86.632, abs=1e-4)
    assert w.odczyt_zadany == pytest.approx(2.632, abs=1e-4)
    assert w.wykonalne is True


def test_odczyt_wiekszy_od_zadanego_znaczy_przeglebienie():
    w = wytycz(rzedna_repera=85.20, odczyt_wstecz=1.432,
               rzedna_projektowa=84.00, odczyt_zmierzony=2.732)
    assert w.roznica == pytest.approx(-0.100, abs=1e-4)
    assert "ZA NISKO" in w.ocena


def test_odczyt_mniejszy_od_zadanego_znaczy_za_wysoko():
    w = wytycz(rzedna_repera=85.20, odczyt_wstecz=1.432,
               rzedna_projektowa=84.00, odczyt_zmierzony=2.532)
    assert w.roznica == pytest.approx(0.100, abs=1e-4)
    assert "ZA WYSOKO" in w.ocena


def test_w_tolerancji_jest_ok():
    w = wytycz(rzedna_repera=85.20, odczyt_wstecz=1.432,
               rzedna_projektowa=84.00, odczyt_zmierzony=2.637, tolerancja_m=0.01)
    assert w.ocena == "OK"


def test_celowa_ponizej_punktu_jest_niewykonalna():
    """Reper nizszy niz punkt docelowy - z tego stanowiska sie nie da."""
    w = wytycz(rzedna_repera=80.98, odczyt_wstecz=1.432, rzedna_projektowa=82.76)
    assert w.wykonalne is False
    assert "PONIZEJ" in w.uwaga


def test_odczyt_poza_dlugoscia_laty_jest_niewykonalny():
    w = wytycz(rzedna_repera=90.00, odczyt_wstecz=1.500, rzedna_projektowa=85.00)
    assert w.wykonalne is False
    assert "laty" in w.uwaga


def test_rzedna_posrednia_wzdluz_odcinka():
    """Wyl101-D155: 20.5 m przy 3 promilach daje 0.0615 m roznicy."""
    assert rzedna_posrednia(82.76, 3.0, 20.5) == pytest.approx(82.6985, abs=1e-4)
    assert rzedna_posrednia(82.76, 3.0, 0) == pytest.approx(82.76, abs=1e-4)


def test_spadek_z_rzednych():
    assert spadek_z_rzednych(82.76, 82.70, 20.5) == pytest.approx(2.927, abs=1e-3)
    assert spadek_z_rzednych(82.76, 82.70, 0) is None


def test_przykrycie_liczy_sie_od_wierzchu_rury():
    # dno 82.76, Ø500 -> wierzch rury 83.26; teren 83.81 -> przykrycie 0.55
    assert przykrycie(83.81, 82.76, 500) == pytest.approx(0.55, abs=1e-3)
    assert przykrycie(83.81, 82.76, None) is None


def test_ciag_niwelacyjny_w_normie():
    c = CiagNiwelacyjny(
        stanowiska=[(1.500, 1.200), (1.400, 1.700), (1.100, 1.100)],
        rzedna_poczatkowa=100.000,
        rzedna_koncowa_dana=100.000,
        dlugosc_km=0.5,
    )
    assert c.przewyzszenie() == pytest.approx(0.0, abs=1e-4)
    assert c.odchylka() == pytest.approx(0.0, abs=1e-4)
    assert c.czy_ok() is True


def test_ciag_niwelacyjny_poza_norma():
    c = CiagNiwelacyjny(
        stanowiska=[(1.500, 1.200)],
        rzedna_poczatkowa=100.000,
        rzedna_koncowa_dana=100.000,
        dlugosc_km=0.1,
    )
    # przewyzszenie +0.300 m przy dopuszczalnej odchylce 20mm*sqrt(0.1) = 6.3 mm
    assert c.odchylka() == pytest.approx(0.300, abs=1e-4)
    assert c.odchylka_dopuszczalna_m() == pytest.approx(0.0063, abs=1e-4)
    assert c.czy_ok() is False
