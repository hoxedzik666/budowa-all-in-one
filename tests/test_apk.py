"""Wpiecie funkcji telefonu w strony Flaska i projekt aplikacji Android.

Zasada calego rozwiazania: **te same szablony obsluguja przegladarke i APK**.
Przyciski natywne zapalaja sie warunkiem `window.Capacitor !== undefined`,
a nie osobnym zestawem widokow. Te testy pilnuja, zeby ten warunek nie
przestal dzialac po jednej stronie albo po drugiej.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import wymaga_pymupdf

KATALOG_APK = Path(__file__).resolve().parent.parent / ".apk"


def czytaj(sciezka: Path) -> str:
    return sciezka.read_text(encoding="utf-8")


# ------------------------------------------------ wpiecie w strony Flaska


def test_skrypt_telefonu_laduje_sie_wszedzie(klient):
    """Jeden plik na kazdej stronie - inaczej skaner dzialalby raz tu, raz tam."""
    for adres in ("/", "/szukaj?q=D155", "/mapa?strona=2", "/raporty"):
        assert "js/telefon.js" in klient.get(adres).get_data(as_text=True), adres


def test_przyciski_natywne_sa_ukryte_poza_aplikacja(klient):
    """W przegladarce aparat i GPS nie istnieja - przycisk do nich prowadzilby
    donikad, wiec ma go nie byc widac."""
    tresc = klient.get("/").get_data(as_text=True)
    assert "[data-tylko-apk] { display: none !important; }" in tresc
    assert 'html[data-apk="1"] [data-tylko-apk]' in tresc


def test_skaner_qr_jest_w_pasku_wyszukiwarki(klient):
    tresc = klient.get("/").get_data(as_text=True)
    assert "data-skanuj" in tresc
    # Przycisk musi byc oznaczony jako natywny, inaczej pokazalby sie
    # w przegladarce i nic nie robil.
    assert "data-skanuj data-tylko-apk" in tresc


@wymaga_pymupdf
def test_gps_jest_na_mapie(klient):
    tresc = klient.get("/mapa?strona=2").get_data(as_text=True)
    assert "gdzie-jestem" in tresc
    assert "/api/mapa/z-gps/" in tresc
    assert "warstwy.gps" in tresc


@wymaga_pymupdf
def test_mapa_ostrzega_ze_gps_nie_nadaje_sie_do_tyczenia(klient):
    """GPS z telefonu ma 3-10 m. Ladny znacznik na mapie kusi, zeby o tym
    zapomniec - dlatego ostrzezenie jest w dymku, a nie w dokumentacji."""
    tresc = klient.get("/mapa?strona=2").get_data(as_text=True)
    assert "Za mało dokładne do tyczenia" in tresc


@pytest.mark.usefixtures("wymaga_danych")
def test_aparat_przy_karcie_odcinka(klient):
    tresc = klient.get("/szukaj?q=D155").get_data(as_text=True)
    assert "data-zdjecie=" in tresc
    assert "data-tylko-apk" in tresc


def test_aparat_w_raporcie_bierze_odcinek_z_formularza(klient):
    """Zeby nie trzeba bylo wpisywac odcinka drugi raz przy zdjeciu."""
    tresc = klient.get("/raporty").get_data(as_text=True)
    assert 'data-dotyczy-z="[name=dotyczy]"' in tresc


def test_zmiana_adresu_serwera_jest_w_menu(klient):
    """Serwer dostaje inne IP z DHCP - bez tego trzeba by reinstalowac aplikacje."""
    assert "data-zmien-serwer" in klient.get("/").get_data(as_text=True)


# ---------------------------------------------------- projekt aplikacji


@pytest.fixture(scope="module")
def katalog_apk():
    if not KATALOG_APK.exists():
        pytest.skip("Brak katalogu .apk")
    return KATALOG_APK


def test_wersje_sa_przypiete(katalog_apk):
    """'Najnowsze' wersje Capacitora i SDK rozjezdzaja sie ze soba, a komunikat
    bledu rzadko wskazuje prawdziwa przyczyne."""
    paczka = json.loads(czytaj(katalog_apk / "package.json"))
    for nazwa, wersja in paczka["dependencies"].items():
        assert not wersja.startswith(("^", "~", "*")), f"{nazwa} nie ma przypietej wersji"


def test_adres_serwera_nie_jest_wbity_w_konfiguracje(katalog_apk):
    """Przy DHCP wbity adres oznaczalby nowy APK dla calej ekipy po kazdej
    zmianie IP. Adres ma pochodzic z ustawien telefonu."""
    konfiguracja = json.loads(czytaj(katalog_apk / "capacitor.config.json"))
    assert "url" not in konfiguracja.get("server", {}), (
        "server.url w pliku konfiguracyjnym zabetonowalby adres serwera"
    )


def test_konfiguracja_dopuszcza_polaczenia_lokalne(katalog_apk):
    konfiguracja = json.loads(czytaj(katalog_apk / "capacitor.config.json"))
    assert konfiguracja["server"]["cleartext"] is True
    assert konfiguracja["appId"] == "pl.budowa.allinone"


def test_manifest_prosi_o_potrzebne_uprawnienia(katalog_apk):
    manifest = czytaj(katalog_apk / "natywne/app/src/main/AndroidManifest.xml")
    for uprawnienie in ("INTERNET", "ACCESS_FINE_LOCATION", "CAMERA"):
        assert uprawnienie in manifest, f"brak uprawnienia {uprawnienie}"
    # Serwer na budowie stoi po HTTP - bez tego Android zablokuje polaczenie.
    assert 'android:usesCleartextTraffic="true"' in manifest


def test_aparat_i_gps_sa_opcjonalne(katalog_apk):
    """Tablet bez aparatu ma nadal pokazywac rzedne i spadki."""
    manifest = czytaj(katalog_apk / "natywne/app/src/main/AndroidManifest.xml")
    assert 'android:name="android.hardware.camera" android:required="false"' in manifest


def test_aktywnosc_czyta_adres_z_ustawien_telefonu(katalog_apk):
    """Sedno calego rozwiazania: most Capacitora powstaje z adresem zapisanym
    w telefonie, a nie z pliku wbudowanego w APK."""
    zrodlo = czytaj(
        katalog_apk / "natywne/app/src/main/java/pl/budowa/allinone/MainActivity.java")
    assert "setServerUrl" in zrodlo
    assert "getSharedPreferences" in zrodlo
    # Config musi trafic do pola PRZED super.onCreate(), bo to ono wola load().
    # Szukamy faktycznego wywolania, nie wzmianki w komentarzu.
    wywolanie = zrodlo.index("super.onCreate(savedInstanceState);")
    assert zrodlo.index("this.config = new") < wywolanie


def test_klucz_adresu_jest_ten_sam_po_obu_stronach(katalog_apk):
    """Java zapisuje, JavaScript czyta - literowka w kluczu oznaczalaby ekran
    konfiguracji przy kazdym uruchomieniu."""
    zrodlo = czytaj(
        katalog_apk / "natywne/app/src/main/java/pl/budowa/allinone/MainActivity.java")
    powloka = czytaj(katalog_apk / "web/shell.js")
    assert 'KLUCZ_ADRESU = "adres_serwera"' in zrodlo
    assert 'KLUCZ = "adres_serwera"' in powloka


def test_przycisk_wstecz_nie_zamyka_aplikacji(katalog_apk):
    """Jedno nieuwazne dotkniecie nie moze wyrzucic brygadzisty z karty odcinka,
    gdy stoi w wykopie i odczytuje rzedna."""
    zrodlo = czytaj(
        katalog_apk / "natywne/app/src/main/java/pl/budowa/allinone/MainActivity.java")
    assert "onBackPressed" in zrodlo
    assert "canGoBack" in zrodlo


def test_ekran_konfiguracji_sprawdza_serwer_przed_zapisem(katalog_apk):
    """Lepiej powiedziec 'nie odpowiada' na ekranie wyboru niz wpuscic w biala
    strone bez mozliwosci powrotu."""
    powloka = czytaj(katalog_apk / "web/shell.js")
    assert "/api/zdrowie" in powloka
    assert "AbortController" in powloka


def test_gotowy_apk_jesli_zbudowany(katalog_apk):
    pliki = list((katalog_apk / "wyjscie").glob("*.apk")) \
        if (katalog_apk / "wyjscie").exists() else []
    if not pliki:
        pytest.skip("APK nie jest jeszcze zbudowany.")
    # Ponizej 5 MB znaczyloby, ze cos nie weszlo do paczki.
    assert pliki[0].stat().st_size > 5 * 1024 * 1024
