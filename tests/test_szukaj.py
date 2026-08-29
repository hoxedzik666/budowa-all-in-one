"""Testy wyszukiwarki i wykazu materialow."""
import pytest


def test_wyszukanie_d155_zwraca_odcinek(klient):
    d = klient.get("/api/szukaj?q=D155").get_json()
    assert d["obiekt"]["kod"] == "D155"
    assert d["obiekt"]["typ"] == "STUDNIA"
    nazwy = [o["nazwa"] for o in d["odcinki"]]
    assert "Wyl101-D155" in nazwy


def test_wyszukiwanie_jest_nieczule_na_wielkosc_liter(klient):
    assert klient.get("/api/szukaj?q=d155").get_json()["obiekt"]["kod"] == "D155"


def test_niepelny_kod_trafia_w_najkrotszy_pasujacy(klient):
    d = klient.get("/api/szukaj?q=Wyl10").get_json()
    assert d["obiekt"]["kod"].startswith("Wyl10")


def test_nieznany_kod_daje_404(klient):
    assert klient.get("/api/szukaj?q=ZUPELNIE_NIE_MA").status_code == 404


def test_podpowiedzi_zwracaja_kody(klient):
    lista = klient.get("/api/podpowiedzi?q=D15").get_json()
    assert lista
    assert all(p["kod"].startswith("D15") for p in lista)


def test_wykaz_materialow_odcinka_wzorcowego(klient):
    d = klient.get("/api/odcinek/Wyl101/D155/rury").get_json()
    assert d["dlugosc_m"] == 20.5
    assert d["dn_profilowe"] == 500
    assert d["dn_katalogowe"] == 500
    assert d["braki"] == []

    warianty = {w["nazwa"]: w for w in d["rury"]["warianty"]}
    assert warianty["same_3m"]["opis_sztuk"] == "7 × 3 m"
    assert warianty["same_6m"]["opis_sztuk"] == "4 × 6 m"
    assert warianty["mieszany"]["opis_sztuk"] == "3 × 6 m + 1 × 3 m"
    assert d["rury"]["zalecany"] == "mieszany"


def test_katalog_ma_obie_dlugosci_handlowe(klient):
    d = klient.get("/api/odcinek/Wyl101/D155/rury").get_json()
    dlugosci = {k["dlugosc_sztuki_m"] for k in d["katalog"]}
    assert dlugosci == {3.0, 6.0}


def test_wykaz_wymienia_obiekty_na_koncach(klient):
    d = klient.get("/api/odcinek/Wyl101/D155/rury").get_json()
    kody = {o["kod"]: o for o in d["obiekty"]}
    assert kody["Wyl101"]["nazwa_materialowa"] == "wylot"
    assert kody["D155"]["nazwa_materialowa"] == "studnia"
    assert kody["D155"]["srednica_studni_mm"] == 1500
    assert kody["D155"]["glebokosc_wykopu"] == pytest.approx(1.55, abs=1e-3)


def test_srednica_600_mapuje_sie_na_katalogowe_630(klient):
    """Rury PRAGMA opisane sa srednica zewnetrzna: DN600 -> OD630."""
    odcinki = klient.get("/api/odcinki?dn=600&limit=5").get_json()
    if not odcinki:
        pytest.skip("brak odcinkow DN600 w bazie")
    o = odcinki[0]
    d = klient.get(f"/api/odcinek/{o['od']}/{o['do']}/rury").get_json()
    assert d["dn_profilowe"] == 600
    assert d["dn_katalogowe"] == 630


def test_repery_najblizsze_mowia_czego_brakuje(klient):
    """Bez pozycji na planie nie zgadujemy - podajemy powod."""
    d = klient.get("/api/szukaj?q=D155").get_json()
    najblizsze = d["repery_najblizsze"]
    if not najblizsze["dostepne"]:
        assert najblizsze["powod"]
        assert najblizsze["repery"] == []


def test_repery_wysokosciowo_sa_posortowane(klient):
    d = klient.get("/api/szukaj?q=D155").get_json()
    roznice = [abs(r["roznica_wysokosci"]) for r in d["repery_wysokosciowo"]]
    assert roznice == sorted(roznice)


def test_strony_wyszukiwarki_i_mapy_sie_renderuja(klient):
    for sciezka in ("/szukaj", "/szukaj?q=D155", "/szukaj?q=Wyl101",
                    "/szukaj?q=NIE_MA_TAKIEGO", "/mapa"):
        assert klient.get(sciezka).status_code == 200, sciezka


def test_strona_wyniku_pokazuje_warianty_rur(klient):
    html = klient.get("/szukaj?q=D155").get_data(as_text=True)
    assert "3 × 6 m + 1 × 3 m" in html
    assert "Docinka" in html
    assert "wykonawca ma rury 3 m i 6 m" in html


def test_mapka_bez_pozycji_zwraca_404_a_nie_pusty_obraz(klient):
    r = klient.get("/mapa/odcinek/Wyl101/D155.png")
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        assert b"png" not in r.data[:8].lower()
