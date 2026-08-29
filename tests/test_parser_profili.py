"""Testy parsera PDF na prawdziwym pliku dokumentacji.

Wzorcem jest profil "D155" ze strony 6 - odcinek Wyl101-D155, ktory dalo sie
odczytac recznie z rysunku i sprawdzic co do setnej.
"""
from pathlib import Path

import pytest

from app.services.pdf_profile_parser import ProfileParser, parsuj_profile

PDF = Path("docs/Profile Scalone.pdf")

pytestmark = pytest.mark.skipif(not PDF.exists(), reason="brak pliku dokumentacji")


@pytest.fixture(scope="module")
def wynik():
    return parsuj_profile(PDF)


def test_wszystkie_strony_maja_legende(wynik):
    assert len(wynik.strony) == 13
    assert wynik.ostrzezenia == []


def test_strona_5_to_kanal_tloczny(wynik):
    """Jedyna strona z pasmem RZEDNA OSI PRZEWODU zamiast RZEDNA DNA KANALU."""
    kt = [s for s in wynik.strony if s["typ_odniesienia"] == "OS_PRZEWODU"]
    assert [s["nr_strony"] for s in kt] == [5]


def test_profil_wzorcowy_wyl101_d155(wynik):
    prof = next(
        p for p in wynik.profile
        if p.nr_strony == 6 and [w.kod for w in p.wezly] == ["Wyl101", "D155"]
    )
    assert prof.oznaczenie == "D155"
    assert prof.poziom_porownawczy == 70.0
    assert prof.typ_odniesienia == "DNO_KANALU"

    wyl, d155 = prof.wezly
    assert wyl.rzedna_dna == 82.70
    assert wyl.rzedna_terenu_proj == 82.70
    assert wyl.zaglebienie == 0.00
    assert wyl.opis == "Wylot"

    assert d155.hektometr == 20.31
    assert d155.rzedna_dna == 82.76
    assert d155.rzedna_terenu_istn == 83.64
    assert d155.rzedna_terenu_proj == 83.81
    assert d155.zaglebienie == 1.05
    assert d155.rzedna_dna_studni == 82.26
    assert d155.srednica_studni_mm == 1500

    odc = prof.odcinki[0]
    assert (odc.od, odc.do) == ("Wyl101", "D155")
    assert odc.dlugosc_m == 20.5
    assert odc.dn_mm == 500
    assert odc.spadek_promile == 3.0  # 0.3%


def test_niezmiennik_zaglebienia_trzyma_sie_w_calym_pliku(wynik):
    """zaglebienie = rzedna terenu proj. - rzedna dna kanalu."""
    sprawdzone = zlamane = 0
    for p in wynik.profile:
        for w in p.wezly:
            if None in (w.rzedna_terenu_proj, w.rzedna_dna, w.zaglebienie):
                continue
            sprawdzone += 1
            if abs((w.rzedna_terenu_proj - w.rzedna_dna) - w.zaglebienie) > 0.015:
                zlamane += 1
    assert sprawdzone > 900
    assert zlamane / sprawdzone < 0.01


def test_zaglebienia_ujemne_sa_dopuszczalne(wynik):
    """Wylot wystajacy ze skarpy ma dno POWYZEJ terenu projektowanego."""
    ujemne = [
        w for p in wynik.profile for w in p.wezly
        if w.zaglebienie is not None and w.zaglebienie < 0
    ]
    assert ujemne, "w dokumentacji sa wyloty z ujemnym zaglebieniem"
    assert all(w.opis is None or "ylot" in w.opis for w in ujemne[:20])


def test_prefiks_sss_jest_obcinany():
    kod, alias = ProfileParser._normalizuj_kod("S.S.S.Wp253")
    assert kod == "Wp253"
    assert alias is None


def test_kod_z_aliasem():
    kod, alias = ProfileParser._normalizuj_kod("KT15=D139")
    assert kod == "KT15"
    assert alias == "D139"


def test_kody_smieciowe_odrzucane():
    for smiec in ("Podpis:", "Nr uprawnień: -", "Specjalność: Sanitarna", "ściek sk."):
        assert ProfileParser._normalizuj_kod(smiec) == (None, None)


def test_pikietaz_rosnie_w_obrebie_profilu(wynik):
    for p in wynik.profile:
        hm = [w.hektometr for w in p.wezly if w.hektometr is not None]
        assert hm == sorted(hm), f"profil {p.oznaczenie} ma nierosnacy pikietaz: {hm}"
