"""Uruchomienie na telefonie: SQLite zamiast Postgresa, brak PyMuPDF, skrypty.

Te testy pilnuja czterech rzeczy, ktore latwo zepsuc przy zwyklej pracy nad
projektem, a ktore widac dopiero na telefonie - czyli za pozno:

1. **Modele musza dzialac na dwoch silnikach.** Jeden `JSONB` wpisany wprost
   w model przewraca cala baze na SQLite.
2. **Aplikacja musi wstawac bez PyMuPDF.** Jeden `import fitz` na poziomie
   modulu wystarczy, zeby w Termuxie nie dalo sie otworzyc nawet niwelatora.
3. **Skrypty musza byc wykonywalne i wskazywac to, co trzeba.**
4. **APK musi umiec wskazac serwer na tym samym telefonie.**

Testy sa napisane tak, zeby przechodzily zarowno w kontenerze (Postgres,
PyMuPDF zainstalowany), jak i na telefonie (SQLite, bez PyMuPDF) - inaczej
sprawdzalyby srodowisko, a nie kod.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql, sqlite

KORZEN = Path(__file__).resolve().parent.parent
KATALOG_TERMUX = KORZEN / "termux"
KATALOG_APK = KORZEN / ".apk"


def czytaj(sciezka: Path) -> str:
    return sciezka.read_text(encoding="utf-8")


# ------------------------------------------------------------------ modele


def test_kolumny_json_dzialaja_na_obu_silnikach():
    """`JSONB` istnieje tylko w Postgresie - na SQLite ma zostac zwykly JSON.

    Wariant typu zalatwia to bez rozgalezien w modelach i **bez zmiany DDL po
    stronie Postgresa**, wiec dzialajace bazy nie wymagaja migracji.
    """
    from app.models.typy import JSON_ELASTYCZNY

    assert "JSONB" in JSON_ELASTYCZNY.compile(dialect=postgresql.dialect())
    assert "JSON" == JSON_ELASTYCZNY.compile(dialect=sqlite.dialect())


def test_zaden_model_nie_deklaruje_jsonb_wprost():
    """JSONB wpisany wprost w model wraca przy pierwszym `create_all` na telefonie."""
    winne = [
        plik.name for plik in (KORZEN / "app" / "models").glob("*.py")
        if plik.name != "typy.py" and "JSONB" in czytaj(plik)
    ]
    assert not winne, f"JSONB wprost w modelach: {winne} - uzyj JSON_ELASTYCZNY"


def test_schemat_dostosowuje_sie_na_sqlite(tmp_path):
    """`flask init-db` ma przejsc na pliku SQLite, i to dwa razy pod rzad.

    Komenda leci przy kazdym uruchomieniu, wiec nieidempotentny krok
    (np. `ADD COLUMN`, ktorego SQLite nie zna z `IF NOT EXISTS`) wywalilby
    aplikacje przy drugim starcie - a nie przy pierwszym, czyli nie przy testach.
    """
    from app import create_app
    from app.config import Config
    from app.extensions import db
    from app.services.schemat import dostosuj_schemat

    plik = tmp_path / "telefon.sqlite3"

    class KonfiguracjaTelefonu(Config):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{plik}"
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}

    aplikacja = create_app(KonfiguracjaTelefonu)
    with aplikacja.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        pierwszy = dostosuj_schemat()
        drugi = dostosuj_schemat()

    assert "uq_connection_naturalny" in pierwszy
    assert pierwszy == drugi, "drugi przebieg zrobil cos innego niz pierwszy"
    assert plik.exists()


def test_konfiguracja_wybiera_sqlite_na_telefonie(monkeypatch):
    from app.config import domyslny_adres_bazy

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TERMUX_VERSION", "0.118.0")
    assert domyslny_adres_bazy().startswith("sqlite:///")

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@c/d")
    assert domyslny_adres_bazy() == "postgresql+psycopg://a:b@c/d", (
        "podany DATABASE_URL musi przebijac wykrywanie Termuxa - inaczej nie da "
        "sie na telefonie postawic Postgresa, gdyby ktos chcial"
    )


def test_sqlite_nie_dostaje_ustawien_puli_sieciowej():
    """SQLite to plik - `pool_recycle` nic tam nie znaczy, a jeden watek to za malo."""
    from app.config import opcje_silnika

    opcje = opcje_silnika("sqlite:////tmp/x.sqlite3")
    assert opcje["connect_args"]["check_same_thread"] is False
    assert "pool_recycle" not in opcje
    assert "pool_recycle" in opcje_silnika("postgresql+psycopg://a:b@c/d")


# --------------------------------------------------------- brak PyMuPDF


MODULY_Z_PDF = [
    "app.blueprints.mapa",
    "app.services.kafelki",
    "app.services.wycinek_pdf",
    "app.services.plan_wektor",
    "app.services.pdf_profile_parser",
    "app.services.plan_ocr",
]


@pytest.mark.parametrize("nazwa", MODULY_Z_PDF)
def test_pdf_nie_jest_importowany_przy_starcie(nazwa):
    """PyMuPDF ma byc siegany dopiero przy uzyciu, nie przy imporcie modulu.

    Gdy `import fitz` stoi na poziomie modulu, brak biblioteki przewraca
    `create_app()` - czyli cala aplikacje, lacznie z niwelatorem i lista zadan,
    ktore z PDF-em nie maja nic wspolnego.
    """
    import importlib

    from app.services.opcjonalne import LeniwyModul

    modul = importlib.import_module(nazwa)
    assert isinstance(modul.fitz, LeniwyModul), (
        f"{nazwa} importuje fitz wprost - bez PyMuPDF aplikacja nie wstanie"
    )


def _aplikacja_z_trasa_ktora_zglasza_brak():
    """Aplikacja z dwiema trasami, ktore udaja funkcje wymagajaca biblioteki.

    Osobna aplikacja, bo trasy dokłada sie przed pierwszym zadaniem, a ta
    z fixture'a obsluzyla juz swoje. Trasy sa sztuczne celowo: prawdziwe (mapa,
    wycinek) zachowuja sie roznie w zaleznosci od tego, co siedzi w bazie
    i jakie pliki leza w `docs/` - a sprawdzamy tu **obsluge bledu**, nie mape.
    """
    from app import create_app
    from app.services.opcjonalne import BrakModulu

    aplikacja = create_app()
    aplikacja.config["WYMAGAJ_LOGOWANIA"] = False

    def _zglos():
        raise BrakModulu(
            "biblioteka_ktorej_nie_ma", "próbę", "Nic nie rób, to tylko test.")

    aplikacja.add_url_rule("/proba-braku-biblioteki", "proba_html", _zglos)
    aplikacja.add_url_rule("/api/proba-braku-biblioteki", "proba_json", _zglos)
    return aplikacja


def test_brak_biblioteki_daje_czytelna_strone():
    """Zamiast bledu 500 uzytkownik ma dostac zdanie, ktore mowi, co zrobic."""
    odpowiedz = _aplikacja_z_trasa_ktora_zglasza_brak().test_client().get(
        "/proba-braku-biblioteki")
    tresc = odpowiedz.get_data(as_text=True)

    assert odpowiedz.status_code == 503, "to nie jest awaria programu, tylko brak funkcji"
    assert "Tej funkcji nie zrobię na tym urządzeniu" in tresc
    assert "biblioteka_ktorej_nie_ma" in tresc
    assert "Nic nie rób, to tylko test." in tresc


def test_brak_biblioteki_w_api_jest_jsonem():
    """Front-end (jQuery) dostaje JSON, a nie strone HTML do wyswietlenia w tabelce."""
    odpowiedz = _aplikacja_z_trasa_ktora_zglasza_brak().test_client().get(
        "/api/proba-braku-biblioteki")

    assert odpowiedz.status_code == 503
    dane = odpowiedz.get_json()
    assert dane["blad"] == "brak_biblioteki"
    assert dane["biblioteka"] == "biblioteka_ktorej_nie_ma"
    assert dane["co_zrobic"]


def test_zdrowie_mowi_na_czym_stoi(klient):
    """Adres serwera w APK sprawdza sie tym wlasnie zadaniem - pole `status` zostaje."""
    dane = klient.get("/api/zdrowie").get_json()

    assert dane["status"] == "ok"
    assert dane["baza"] in {"postgresql", "sqlite"}
    assert "fitz" in dane["moduly"]
    assert isinstance(dane["moduly"]["fitz"], bool)


def test_opcjonalny_modul_nie_wybucha_przy_imporcie():
    from app.services.opcjonalne import BrakModulu, LeniwyModul

    modul = LeniwyModul("nie_ma_takiej_biblioteki_2137")  # sam import przechodzi
    with pytest.raises(BrakModulu) as blad:
        modul.cokolwiek

    assert blad.value.nazwa == "nie_ma_takiej_biblioteki_2137"
    assert blad.value.jak_naprawic


# ------------------------------------------------------ zaleznosci i skrypty


def _wersje(plik: Path) -> dict[str, str]:
    wynik = {}
    for linia in czytaj(plik).splitlines():
        linia = linia.strip()
        if not linia or linia.startswith("#") or "==" not in linia:
            continue
        nazwa, wersja = linia.split("==", 1)
        wynik[nazwa.lower()] = wersja
    return wynik


def test_lista_dla_telefonu_nie_ma_tego_co_sie_nie_zainstaluje():
    tresc = _wersje(KORZEN / "requirements-termux.txt")
    for zakazane in ("pymupdf", "psycopg", "psycopg[binary]", "pyproj", "pytesseract"):
        assert zakazane not in tresc, f"{zakazane} nie zainstaluje sie w Termuxie"


def test_wersje_dla_telefonu_zgadzaja_sie_z_komputerem():
    """Ta sama biblioteka w dwoch wersjach to blad, ktory wychodzi tylko na telefonie."""
    komputer = _wersje(KORZEN / "requirements.txt")
    telefon = _wersje(KORZEN / "requirements-termux.txt")

    rozjazd = {
        nazwa: (telefon[nazwa], komputer[nazwa])
        for nazwa in telefon if nazwa in komputer and telefon[nazwa] != komputer[nazwa]
    }
    assert not rozjazd, f"rozjechane wersje (telefon, komputer): {rozjazd}"


@pytest.mark.parametrize("nazwa", ["instaluj.sh", "uruchom.sh", "autostart.sh"])
def test_skrypty_termuxa_sa_wykonywalne(nazwa):
    plik = KATALOG_TERMUX / nazwa
    assert plik.exists(), f"brak {plik}"
    assert os.stat(plik).st_mode & stat.S_IXUSR, (
        f"{nazwa} bez prawa wykonywania - w Termuxie trzeba by pamietac o chmod"
    )


def test_instalator_bierze_liste_dla_telefonu():
    tresc = czytaj(KATALOG_TERMUX / "instaluj.sh")
    assert "requirements-termux.txt" in tresc
    assert "requirements.txt\n" not in tresc.replace("requirements-termux.txt", "")


def test_serwer_domyslnie_slucha_tylko_na_tym_telefonie():
    """Serwer w obcej sieci nie ma sie wystawiac sam z siebie - haslo idzie po HTTP."""
    tresc = czytaj(KATALOG_TERMUX / "uruchom.sh")
    assert 'ADRES="127.0.0.1"' in tresc
    assert "--siec" in tresc, "musi byc sposob, zeby swiadomie wpuscic brygade"
    assert "termux-wake-lock" in tresc, "bez rygla Android uspi serwer w polowie zapisu"


# ------------------------------------------------------------------- APK


def test_apk_umie_wskazac_serwer_na_tym_samym_telefonie():
    strona = czytaj(KATALOG_APK / "web" / "index.html")
    skrypt = czytaj(KATALOG_APK / "web" / "shell.js")

    assert 'id="ten-telefon"' in strona
    assert "127.0.0.1:8000" in skrypt
    assert "ten-telefon" in skrypt


def test_ekran_bledu_istnieje_i_jest_wskazany_w_konfiguracji():
    """Bez `errorPath` niedzialajacy serwer to bialy ekran bez slowa wyjasnienia."""
    konfiguracja = json.loads(czytaj(KATALOG_APK / "capacitor.config.json"))
    sciezka = konfiguracja["server"]["errorPath"]
    strona = KATALOG_APK / konfiguracja["webDir"] / sciezka

    assert strona.exists(), f"errorPath wskazuje na nieistniejacy plik: {sciezka}"
    assert "termux/uruchom.sh" in czytaj(strona), (
        "ekran bledu ma mowic, co zrobic - najczestsza przyczyna to nieuruchomiony serwer"
    )


def test_ekran_bledu_uzywa_tego_samego_klucza_adresu():
    """Ten sam klucz co shell.js i MainActivity - inaczej 'Sprobuj ponownie' nie ma dokad."""
    assert '"adres_serwera"' in czytaj(KATALOG_APK / "web" / "blad.html")
