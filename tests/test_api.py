"""Testy API na zaimportowanej bazie."""
import pytest


def test_zdrowie(klient):
    assert klient.get("/api/zdrowie").get_json() == {"status": "ok"}


def test_statystyki_maja_dane(klient):
    d = klient.get("/api/statystyki").get_json()
    assert d["profile"] > 400
    assert d["obiekty"] > 1000
    assert d["odcinki"] > 600
    assert d["punkty_osnowy"] == 151
    assert d["dlugosc_calkowita_m"] > 7000


def test_odcinek_wzorcowy(klient):
    d = klient.get("/api/odcinki/Wyl101/D155").get_json()
    assert d["dlugosc_m"] == 20.5
    assert d["dn_mm"] == 500
    assert d["spadek_promile"] == 3.0
    assert d["spadek_procent"] == 0.3
    assert d["obiekt_do"]["rzedna_dna_kanalu"] == 82.76
    assert d["obiekt_do"]["rzedna_dna_studni"] == 82.26
    assert d["obiekt_do"]["glebokosc_wykopu"] == 1.55


def test_obiekt_ma_wystapienia_i_polaczenia(klient):
    d = klient.get("/api/obiekty/D155").get_json()
    assert d["kod"] == "D155"
    assert d["typ"] == "STUDNIA"
    assert len(d["wystapienia"]) >= 1


def test_graf_polaczen_z_arkusza_wpustow(klient):
    """Kolumna "Odbiornik" z XLSX: Wp133 odplywa do D6."""
    d = klient.get("/api/obiekty/Wp133").get_json()
    odbiorniki = [c["obiekt_zrodlowy"] for c in d["polaczenia"] if c["kierunek"] == "ODPLYW"]
    assert "D6" in odbiorniki


def test_brak_kodow_z_prefiksem_sss(klient):
    d = klient.get("/api/obiekty?szukaj=S.S.S&limit=50").get_json()
    assert d == []


def test_niwelator_liczy_odczyt_zadany(klient):
    d = klient.post("/niwelator/oblicz", json={
        "rzedna_repera": 85.20, "odczyt_wstecz": 1.432,
        "obiekt": "D155", "cel": "dno_kanalu",
    }).get_json()
    assert d["hi"] == pytest.approx(86.632, abs=1e-3)
    assert d["rzedna_projektowa"] == 82.76
    assert d["odczyt_zadany"] == pytest.approx(3.872, abs=1e-3)
    assert d["przykrycie"] == pytest.approx(0.55, abs=1e-3)


def test_niwelator_wymaga_repera(klient):
    r = klient.post("/niwelator/oblicz", json={"odczyt_wstecz": 1.0, "obiekt": "D155"})
    assert r.status_code == 400


def test_niwelator_nieznany_obiekt(klient):
    r = klient.post("/niwelator/oblicz", json={
        "rzedna_repera": 85.0, "odczyt_wstecz": 1.0, "obiekt": "NIE_MA_TAKIEGO",
    })
    assert r.status_code in (400, 404)


def test_strony_html_sie_renderuja(klient):
    for sciezka in ("/", "/odcinki", "/obiekty", "/obiekt/D155", "/profile",
                    "/osnowa", "/materialy", "/importy", "/niwelator/"):
        assert klient.get(sciezka).status_code == 200, sciezka


def test_rysunek_profilu_sie_renderuje(klient):
    """Pikietaz pierwszego wezla to zwykle 0.00 - filtr nie moze go zgubic."""
    dane = klient.get("/api/odcinki/Wyl101/D155").get_json()
    html = klient.get(f"/profil/{dane['profil_id']}").get_data(as_text=True)
    assert "linia-dna" in html
    assert "Wyl101" in html and "D155" in html
    assert "Za malo danych" not in html
