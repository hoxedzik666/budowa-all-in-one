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


# ------------------------------------------------- jedno polecenie: start.sh


def test_start_jest_wykonywalny_w_korzeniu():
    """Pierwsze, co widac po sklonowaniu - i ma dzialac bez `chmod`."""
    plik = KORZEN / "start.sh"
    assert plik.exists(), "brak start.sh w katalogu glownym"
    assert os.stat(plik).st_mode & stat.S_IXUSR


def test_start_instaluje_i_uruchamia():
    tresc = czytaj(KORZEN / "start.sh")
    assert "termux/instaluj.sh" in tresc, "pierwsze uruchomienie ma samo doinstalowac"
    assert "termux/uruchom.sh --otworz" in tresc, "ma tez otworzyc strone"
    assert "TERMUX_VERSION" in tresc and "com.termux" in tresc, (
        "poza Termuxem skrypt ma powiedziec, ze na komputerze idzie sie Dockerem"
    )
    assert "ADMIN_LOGIN" in tresc and "ADMIN_HASLO" in tresc, (
        "bez pokazania hasla strona dziala, ale nie da sie do niej wejsc"
    )


def test_otwarcie_przegladarki_nie_moze_przewrocic_serwera():
    """Brak Termux:API to nie powod, zeby serwer nie wstal."""
    tresc = czytaj(KATALOG_TERMUX / "uruchom.sh")
    assert "--otworz" in tresc
    assert "termux-open-url" in tresc
    assert "android.intent.action.VIEW" in tresc, "zapas dla telefonow bez Termux:API"
    assert tresc.count("|| true") >= 2, "kazda proba otwarcia ma byc nieobowiazkowa"


def test_instalator_wgrywa_baze_startowa_tylko_gdy_bazy_nie_ma():
    """Istniejaca baza to dane budowy - pomiary, raporty i zdjecia z wykopu."""
    tresc = czytaj(KATALOG_TERMUX / "instaluj.sh")
    assert "baza-startowa/budowa.sqlite3" in tresc
    assert "if [ ! -f data/budowa.sqlite3 ]" in tresc, (
        "kopiowanie bez tego warunku nadpisaloby prace calej brygady"
    )


# ------------------------------------------------------------ baza startowa

BAZA_STARTOWA = KORZEN / "data" / "baza-startowa" / "budowa.sqlite3"

# Liczby z importu dokumentacji DK29 - te same, ktore wypisuje `flask statystyki`
# i ktore stoja w README. Spadek ktorejkolwiek znaczy, ze do repozytorium trafil
# zrzut z niepelnego albo zepsutego importu.
MINIMUM_W_BAZIE = {
    "sheet": 13,
    "profile": 465,
    "network_object": 1059,
    "segment": 649,
    "connection": 880,
    "survey_point": 151,
    "material_item": 32,
}


def _polacz_z_baza_startowa():
    import sqlite3

    return sqlite3.connect(f"file:{BAZA_STARTOWA}?mode=ro", uri=True)


def test_baza_startowa_lezy_w_repozytorium():
    """Bez niej swiezo zainstalowany telefon pokazuje pusta wyszukiwarke.

    Import z PDF wymaga PyMuPDF, ktorego na Androidzie nie ma, wiec dokumentacja
    trafia na telefon jako gotowy plik - inaczej do uruchomienia narzedzia
    potrzebny bylby komputer z Dockerem.
    """
    assert BAZA_STARTOWA.exists(), (
        "brak data/baza-startowa/budowa.sqlite3 - odtworz komenda "
        "`flask zrzut-sqlite data/baza-startowa/budowa.sqlite3 --tylko-dokumentacja`"
    )
    assert BAZA_STARTOWA.stat().st_size > 500_000, "plik jest podejrzanie maly"


def test_baza_startowa_jest_samowystarczalna():
    """Obok bazy nie moze lezec dziennik WAL.

    Kazde otwarcie bazy w trybie WAL tworzy pliki `-wal` i `-shm`. Zatwierdzone
    razem z baza sa smieciem, ktory przy kolejnym klonowaniu udaje niedokonczona
    transakcje. Plik w repozytorium jest wiec w trybie `delete`; tryb WAL wlacza
    aplikacja na swojej kopii roboczej (app/services/baza.py).
    """
    import sqlite3

    towarzyszace = [
        p.name for p in BAZA_STARTOWA.parent.iterdir()
        if p.suffix in (".sqlite3-wal", ".sqlite3-shm")
        or p.name.endswith(("-wal", "-shm"))
    ]
    assert not towarzyszace, f"pliki dziennika obok bazy startowej: {towarzyszace}"

    baza = sqlite3.connect(f"file:{BAZA_STARTOWA}?mode=ro", uri=True)
    try:
        assert baza.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        baza.close()


def test_baza_startowa_ma_cala_dokumentacje():
    baza = _polacz_z_baza_startowa()
    try:
        assert baza.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for tabela, ile in MINIMUM_W_BAZIE.items():
            wynik = baza.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
            assert wynik == ile, f"{tabela}: {wynik} zamiast {ile}"
        dlugosc = baza.execute("SELECT sum(dlugosc_m) FROM segment").fetchone()[0]
        assert abs(float(dlugosc) - 7439.5) < 0.1, f"laczna dlugosc sieci: {dlugosc}"
    finally:
        baza.close()


def test_baza_startowa_nie_niesie_zadnych_ludzi():
    """To jest test prywatnosci, nie kosmetyka.

    Plik lezy w repozytorium, wiec widzi go kazdy, kto sklonuje projekt. Konta
    (razem ze skrotami hasel), raporty dzienne, pomiary z wykopu i zdjecia sa
    danymi konkretnych osob i konkretnej budowy - w bazie startowej nie moze byc
    ani jednego takiego wiersza.
    """
    from app.cli import TABELE_LUDZI

    baza = _polacz_z_baza_startowa()
    try:
        niepuste = {
            tabela: baza.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
            for tabela in sorted(TABELE_LUDZI)
        }
    finally:
        baza.close()

    assert not any(niepuste.values()), f"dane ludzi w bazie startowej: {niepuste}"


def test_zrzut_bez_flagi_bierze_wszystko_a_z_flaga_pomija_ludzi(app, konto_testowe, tmp_path):
    """Flaga rozstrzyga o tym, co wyjedzie z serwera - warto to sprawdzac.

    Bez niej `zrzut-sqlite` sluzy do przeniesienia bazy **swojej** ekipy na
    telefon, wiec konta i raporty maja przejsc. Z nia powstaje plik startowy
    dla repozytorium i wtedy nie moze przejsc nic, co dotyczy ludzi.
    """
    import sqlite3

    def ile_kont(plik: Path) -> int:
        baza = sqlite3.connect(plik)
        try:
            return baza.execute("SELECT count(*) FROM uzytkownik").fetchone()[0]
        finally:
            baza.close()

    biegacz = app.test_cli_runner()

    pelny = tmp_path / "pelny.sqlite3"
    wynik = biegacz.invoke(args=["zrzut-sqlite", str(pelny)])
    assert wynik.exit_code == 0, wynik.output
    assert ile_kont(pelny) >= 1, "pelny zrzut ma przeniesc konta ekipy"

    startowy = tmp_path / "startowy.sqlite3"
    wynik = biegacz.invoke(args=["zrzut-sqlite", str(startowy), "--tylko-dokumentacja"])
    assert wynik.exit_code == 0, wynik.output
    assert ile_kont(startowy) == 0, "zrzut dla repozytorium nie moze niesc kont"
    assert "pominieta" in wynik.output


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
