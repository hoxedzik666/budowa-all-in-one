"""Dziennik wykonawczy, praca offline i kody QR.

Najwazniejsza rzecz sprawdzana tutaj: **pomiar nie nadpisuje projektu**.
Gdyby nadpisywal, po tygodniu nikt nie odroznilby tego, co zaprojektowano,
od tego, co zbudowano - a caly sens dziennika lezy wlasnie w tej roznicy.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import (
    NetworkObject,
    PomiarWykonawczy,
    RodzajPomiaru,
    Segment,
    spadek_wykonany,
)


class SztucznyOdcinek:
    """Odcinek Wyl101-D155 z dokumentacji: 20,5 m, spadek 3 promile."""

    nazwa = "Wyl101-D155"
    rzedna_dna_od = 82.70
    rzedna_dna_do = 82.76
    dlugosc_m = 20.5
    spadek_promile = 3.0


def pomiar(**pola) -> PomiarWykonawczy:
    dane = {"rodzaj": RodzajPomiaru.DNO_KANALU}
    dane.update(pola)
    p = PomiarWykonawczy(**{k: v for k, v in dane.items() if k != "segment"})
    if "segment" in dane:
        p.segment = dane["segment"]
    return p


# ------------------------------------------------------- rzedna projektowa


def test_odleglosc_liczy_sie_od_pierwszego_obiektu_w_nazwie():
    """Na odcinku Wyl101-D155 metr zerowy jest przy Wyl101.

    To nie jest oczywiste: profile rysuje sie od wylotu w gore, wiec `od`
    bywa nizszym koncem. Interpolacja musi isc wprost od `rzedna_dna_od`
    do `rzedna_dna_do`, bez zgadywania, ktory koniec lezy wyzej.
    """
    odc = SztucznyOdcinek()
    poczatek = pomiar(segment=odc, odleglosc_m=0.0, rzedna_zmierzona=82.70)
    koniec = pomiar(segment=odc, odleglosc_m=20.5, rzedna_zmierzona=82.76)

    assert poczatek.rzedna_projektowa == pytest.approx(82.70)
    assert koniec.rzedna_projektowa == pytest.approx(82.76)


def test_rzedna_w_polowie_odcinka():
    srodek = pomiar(segment=SztucznyOdcinek(), odleglosc_m=10.25, rzedna_zmierzona=82.73)
    assert srodek.rzedna_projektowa == pytest.approx(82.73, abs=0.001)
    assert srodek.odchylka_m == pytest.approx(0.0, abs=0.001)


def test_odleglosc_poza_odcinkiem_nie_ekstrapoluje():
    """Pomiar 100 m na 20-metrowym odcinku to pomylka, nie powod do ekstrapolacji."""
    daleko = pomiar(segment=SztucznyOdcinek(), odleglosc_m=100.0, rzedna_zmierzona=82.0)
    assert daleko.rzedna_projektowa == pytest.approx(82.76)


def test_odchylka_i_tolerancja():
    p = pomiar(segment=SztucznyOdcinek(), odleglosc_m=0.0, rzedna_zmierzona=82.715)
    assert p.odchylka_m == pytest.approx(0.015)
    assert p.tolerancja_m == 0.02
    assert p.w_tolerancji is True

    p.rzedna_zmierzona = 82.74
    assert p.w_tolerancji is False


def test_teren_ma_lagodniejsza_tolerancje_niz_dno():
    """Dno kanalu decyduje o tym, czy woda poplynie. Teren nie."""
    from app.models.wykonanie import TOLERANCJE_M

    assert TOLERANCJE_M["DNO_KANALU"] < TOLERANCJE_M["TEREN"]


def test_brak_danych_projektowych_daje_brak_odchylki():
    class BezRzednych:
        nazwa = "X-Y"
        rzedna_dna_od = None
        rzedna_dna_do = None
        dlugosc_m = 10.0
        spadek_promile = None

    p = pomiar(segment=BezRzednych(), odleglosc_m=1.0, rzedna_zmierzona=50.0)
    assert p.rzedna_projektowa is None
    assert p.odchylka_m is None
    assert p.w_tolerancji is None


# ---------------------------------------------------------- spadek wykonany


def test_spadek_wykonany_z_dwoch_punktow():
    odc = SztucznyOdcinek()
    pomiary = [
        pomiar(segment=odc, odleglosc_m=0.0, rzedna_zmierzona=82.700),
        pomiar(segment=odc, odleglosc_m=20.5, rzedna_zmierzona=82.780),
    ]
    wynik = spadek_wykonany(pomiary, odc)
    assert wynik["dlugosc_m"] == 20.5
    assert wynik["spadek_promile"] == pytest.approx(3.9, abs=0.05)
    assert wynik["poprawny_kierunek"] is True
    assert wynik["roznica_do_projektu_promile"] == pytest.approx(0.9, abs=0.05)


def test_rura_ulozona_w_zla_strone_jest_wykrywana():
    """Rzedne moga byc w tolerancji, a woda i tak nie poplynie."""
    odc = SztucznyOdcinek()
    pomiary = [
        pomiar(segment=odc, odleglosc_m=0.0, rzedna_zmierzona=82.76),
        pomiar(segment=odc, odleglosc_m=20.5, rzedna_zmierzona=82.70),
    ]
    wynik = spadek_wykonany(pomiary, odc)
    assert wynik["poprawny_kierunek"] is False


def test_jeden_pomiar_nie_daje_spadku():
    odc = SztucznyOdcinek()
    assert spadek_wykonany(
        [pomiar(segment=odc, odleglosc_m=0.0, rzedna_zmierzona=82.7)], odc) is None


def test_pomiary_terenu_nie_licza_sie_do_spadku_rury():
    odc = SztucznyOdcinek()
    pomiary = [
        pomiar(segment=odc, odleglosc_m=0.0, rzedna_zmierzona=83.5,
               rodzaj=RodzajPomiaru.TEREN),
        pomiar(segment=odc, odleglosc_m=20.5, rzedna_zmierzona=83.6,
               rodzaj=RodzajPomiaru.TEREN),
    ]
    assert spadek_wykonany(pomiary, odc) is None


# --------------------------------------------------------------- endpointy


@pytest.fixture()
def czysty_dziennik(klient, db):
    db.session.execute(PomiarWykonawczy.__table__.delete())
    db.session.commit()
    yield klient
    db.session.execute(PomiarWykonawczy.__table__.delete())
    db.session.commit()


def test_zapis_pomiaru_nie_rusza_projektu(czysty_dziennik, db):
    """Sedno calego modulu: projekt zostaje nietkniety."""
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    obiekt = db.session.scalar(
        select(NetworkObject).where(NetworkObject.kod == "D155"))
    przed = float(obiekt.rzedna_dna_kanalu)

    odpowiedz = czysty_dziennik.post("/wykonanie/dodaj", data={
        "dotyczy": "Wyl101-D155", "rodzaj": "DNO_KANALU",
        "rzedna": "82,900", "odleglosc": "20,5",
    }, follow_redirects=True)
    assert odpowiedz.status_code == 200

    db.session.expire_all()
    obiekt = db.session.scalar(
        select(NetworkObject).where(NetworkObject.kod == "D155"))
    assert float(obiekt.rzedna_dna_kanalu) == przed, (
        "pomiar wykonawczy nadpisal rzedna projektowa"
    )


def test_api_odcinka_podaje_odchylki(czysty_dziennik, db):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta.")

    for odleglosc, rzedna in (("0", "82,700"), ("20,5", "82,780")):
        czysty_dziennik.post("/wykonanie/dodaj", data={
            "dotyczy": "Wyl101-D155", "rodzaj": "DNO_KANALU",
            "rzedna": rzedna, "odleglosc": odleglosc,
        }, follow_redirects=True)

    dane = czysty_dziennik.get("/api/wykonanie/odcinek/Wyl101/D155").get_json()
    assert dane["pomiarow"] == 2
    assert dane["spadek"]["poprawny_kierunek"] is True
    assert dane["pomiary"][0]["rzedna_projektowa"] == pytest.approx(82.70)


def test_nieznany_odcinek_nie_zapisuje_pomiaru(czysty_dziennik, db):
    czysty_dziennik.post("/wykonanie/dodaj", data={
        "dotyczy": "NIE-MA", "rzedna": "50,0"}, follow_redirects=True)
    assert db.session.scalar(select(func.count()).select_from(PomiarWykonawczy)) == 0


def test_rzedna_z_literami_jest_odrzucana(czysty_dziennik, db):
    czysty_dziennik.post("/wykonanie/dodaj", data={
        "dotyczy": "D155", "rzedna": "osiemdziesiat"}, follow_redirects=True)
    assert db.session.scalar(select(func.count()).select_from(PomiarWykonawczy)) == 0


def test_widok_dziennika_dziala(czysty_dziennik):
    assert czysty_dziennik.get("/wykonanie").status_code == 200
    assert czysty_dziennik.get("/wykonanie?zakres=poza-tolerancja").status_code == 200


# ------------------------------------------------------ offline i kody QR


def test_service_worker_ma_zasieg_calej_aplikacji(klient_anonim):
    """Skrypt musi isc z korzenia, inaczej obslugiwalby tylko /static/."""
    odpowiedz = klient_anonim.get("/service-worker.js")
    assert odpowiedz.status_code == 200
    assert odpowiedz.headers["Service-Worker-Allowed"] == "/"
    assert "javascript" in odpowiedz.mimetype


def test_offline_dziala_bez_zalogowania(klient_anonim):
    """Bez sieci przegladarka nie ma jak sie zalogowac - musi zobaczyc powod."""
    odpowiedz = klient_anonim.get("/offline")
    assert odpowiedz.status_code == 200
    assert "zasięgu" in odpowiedz.get_data(as_text=True)


def test_pozostale_adresy_nadal_wymagaja_logowania(klient_anonim):
    """Otwarcie /offline nie moze byc furtka do reszty aplikacji."""
    for sciezka in ("/wykonanie", "/qr", "/szukaj?q=D155"):
        assert klient_anonim.get(sciezka).status_code == 302


def test_service_worker_nie_zapisuje_zapisow_ani_kafelkow():
    """Pomiar zapisany 'na niby' bylby gorszy niz blad."""
    from pathlib import Path

    from app import create_app

    aplikacja = create_app()
    tresc = (Path(aplikacja.root_path) / "static" / "service-worker.js").read_text(
        encoding="utf-8")
    assert 'zadanie.method !== "GET"' in tresc
    assert "/mapa/kafelek/" in tresc
    assert "/login" in tresc


def test_kod_qr_prowadzi_do_karty_obiektu(klient, db):
    if not db.session.scalar(select(func.count()).select_from(NetworkObject)):
        pytest.skip("Baza pusta.")
    odpowiedz = klient.get("/qr/D155.png")
    assert odpowiedz.status_code == 200
    assert odpowiedz.data.startswith(b"\x89PNG")


def test_kod_qr_nieistniejacego_obiektu_to_404(klient):
    assert klient.get("/qr/NIE-MA.png").status_code == 404


def test_arkusz_kodow_da_sie_wydrukowac(klient):
    tresc = klient.get("/qr?typ=STUDNIA").get_data(as_text=True)
    assert "@media print" in tresc
    assert "bez-druku" in tresc


def test_karta_odcinka_do_druku(klient, db):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta.")
    tresc = klient.get("/odcinek/Wyl101/D155/karta").get_data(as_text=True)
    assert "@page { size: A4 portrait" in tresc
    # Kartka ma dzialac takze jako notatnik, gdy nie ma jeszcze pomiarow.
    assert "puste" in tresc
