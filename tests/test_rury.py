"""Testy przelicznika rur.

Slownictwo, ktore trzeba trzymac konsekwentnie:
  * **docinka** - kawalek, ktory faktycznie ida do wykopu (odcinany z calej rury),
  * **odpad**   - to, co z tej rury zostaje,
  * docinka + odpad = dlugosc calej rury, z ktorej ciano.
"""
import pytest

from app.services.rury import (
    DLUGOSCI_HANDLOWE_M,
    podsumuj,
    przelicz,
    srednica_katalogowa,
    wariant_jednorodny,
    wariant_mieszany,
)


def _wariant(dane, nazwa):
    return next(w for w in dane["warianty"] if w["nazwa"] == nazwa)


def test_wykonawca_ma_rury_3m_i_6m():
    assert DLUGOSCI_HANDLOWE_M == (3.0, 6.0)


# --------------------------------------------------------- srednice katalogowe


@pytest.mark.parametrize("profil,katalog", [
    (200, 200), (250, 250), (400, 400), (500, 500), (1000, 1000),
    (300, 315),   # PRAGMA OD315 = DN300
    (600, 630),   # PRAGMA OD630 = DN600
])
def test_mapowanie_srednic_na_katalog(profil, katalog):
    assert srednica_katalogowa(profil) == katalog


def test_nieznana_srednica_przechodzi_bez_zmian():
    assert srednica_katalogowa(350) == 350
    assert srednica_katalogowa(None) is None


# ------------------------------------------------------- odcinek wzorcowy 20,5


def test_odcinek_wzorcowy_wyl101_d155():
    """20,5 m Ø500 - odcinek, ktory da sie sprawdzic recznie na rysunku."""
    d = przelicz(20.5, 500)
    assert d["dn_katalogowe"] == 500

    same3 = _wariant(d, "same_3m")
    assert same3["sztuk_razem"] == 7          # 6 calych + 1 docinana
    assert same3["material_m"] == 21.0
    assert same3["docinka_m"] == 2.5
    assert same3["odpad_m"] == 0.5
    assert same3["liczba_ciec"] == 1

    same6 = _wariant(d, "same_6m")
    assert same6["sztuk_razem"] == 4
    assert same6["material_m"] == 24.0
    assert same6["docinka_m"] == 2.5
    assert same6["odpad_m"] == 3.5

    mix = _wariant(d, "mieszany")
    assert mix["opis_sztuk"] == "3 × 6 m + 1 × 3 m"
    assert mix["sztuk_razem"] == 4
    assert mix["material_m"] == 21.0
    assert mix["docinka_m"] == 2.5
    assert mix["odpad_m"] == 0.5           # najmniejszy odpad przy 4 sztukach


# ------------------------------------------------------------------- warianty


def test_dlugosc_bez_reszty_nie_wymaga_ciecia():
    d = przelicz(24.0, 400)
    for w in d["warianty"]:
        assert w["liczba_ciec"] == 0
        assert w["odpad_m"] == 0.0
        assert w["docinka_m"] == 0.0


def test_mieszany_wybiera_najmniej_sztuk():
    """9 m: 1×6 + 1×3 to 2 sztuki, same 3 m to az 3."""
    d = przelicz(9.0, 200)
    assert _wariant(d, "mieszany")["sztuk_razem"] == 2
    assert _wariant(d, "same_3m")["sztuk_razem"] == 3
    assert _wariant(d, "mieszany")["odpad_m"] == 0.0


def test_mieszany_przy_remisie_sztuk_wybiera_mniejszy_odpad():
    """78,5 m: 14×6 i 13×6+1×3 to po 14 sztuk - wygrywa mniejszy odpad."""
    d = przelicz(78.5, 500)
    mix, same6 = _wariant(d, "mieszany"), _wariant(d, "same_6m")
    assert mix["sztuk_razem"] == same6["sztuk_razem"] == 14
    assert mix["odpad_m"] == 2.5
    assert same6["odpad_m"] == 5.5


def test_jedna_cala_rura_gdy_dlugosc_rowna_handlowej():
    d = przelicz(6.0, 200)
    assert _wariant(d, "mieszany")["opis_sztuk"] == "1 × 6 m"
    assert _wariant(d, "mieszany")["liczba_ciec"] == 0


# --------------------------------------------------------------- same docinki


def test_odcinek_krotszy_niz_najkrotsza_rura():
    """2,5 m - nie ma z czego zlozyc, cala robota to jedna docinka."""
    d = przelicz(2.5, 200)
    assert "krotszy" in d["uwaga"]
    mix = _wariant(d, "mieszany")
    assert mix["sztuk_razem"] == 1
    assert mix["docinka_m"] == 2.5
    assert mix["odpad_m"] == 0.5
    assert mix["liczba_ciec"] == 1


def test_bardzo_krotki_odcinek():
    d = przelicz(0.5, 200)
    mix = _wariant(d, "mieszany")
    assert mix["docinka_m"] == 0.5
    assert mix["odpad_m"] == 2.5
    assert mix["material_m"] == 3.0


def test_docinka_plus_odpad_rowna_sie_calej_rurze():
    """Niezmiennik: to, co wchodzi do wykopu, plus odpad = dlugosc rury."""
    for dlugosc in (0.5, 2.5, 4.0, 7.7, 20.5, 78.5, 175.0):
        for w in przelicz(dlugosc, 200)["warianty"]:
            if w["liczba_ciec"]:
                najkrotsza = min(p["dlugosc_m"] for p in w["pozycje"])
                assert w["docinka_m"] + w["odpad_m"] == pytest.approx(najkrotsza, abs=1e-6)


def test_material_zawsze_pokrywa_odcinek():
    for dlugosc in (0.5, 2.5, 3.0, 4.0, 9.0, 20.5, 78.5, 175.0):
        for w in przelicz(dlugosc, 200)["warianty"]:
            assert w["material_m"] >= dlugosc - 1e-6, (dlugosc, w["nazwa"])


# ------------------------------------------------------------- braki i sumy


def test_brak_dlugosci_nie_wywala_tylko_informuje():
    d = przelicz(None, 500)
    assert d["warianty"] == []
    assert "dlugosci" in d["uwaga"]


def test_podsumowanie_wielu_odcinkow():
    class Fake:
        def __init__(self, dl, dn, nazwa):
            self.dlugosc_m, self.dn_mm, self.nazwa = dl, dn, nazwa

    wynik = podsumuj([
        Fake(20.5, 500, "A-B"), Fake(9.0, 200, "B-C"),
        Fake(6.0, 200, "C-D"), Fake(None, 400, "D-E"),
    ])
    wg = {s["dn_katalogowe"]: s for s in wynik["srednice"]}
    assert wg[200]["dlugosc_m"] == 15.0
    assert wg[500]["dlugosc_m"] == 20.5
    assert wynik["odcinki_bez_danych"] == ["D-E"]


def test_wariant_jednorodny_i_mieszany_bezposrednio():
    assert wariant_jednorodny(10.0, 3.0).sztuk_razem == 4
    assert wariant_mieszany(10.0).sztuk_razem == 2   # 6 + 6? nie: 6+3=9 <10, wiec 6+6
