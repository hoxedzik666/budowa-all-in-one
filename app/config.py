"""Konfiguracja aplikacji."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

POSTGRES_DOMYSLNY = "postgresql+psycopg://budowa:budowa@localhost:5433/budowa"
SQLITE_TELEFON = BASE_DIR / "data" / "budowa.sqlite3"


def czy_termux() -> bool:
    """Czy program dziala na telefonie, w Termuxie.

    Termux ustawia `TERMUX_VERSION`, a swoje `PREFIX` trzyma w katalogu
    aplikacji. Sprawdzamy oba, bo pierwsza zmienna gubi sie przy uruchomieniu
    z Termux:Boot, a druga jest tam zawsze.
    """
    if os.environ.get("TERMUX_VERSION"):
        return True
    return "com.termux" in os.environ.get("PREFIX", "")


def domyslny_adres_bazy() -> str:
    """Adres bazy, gdy nikt nie podal `DATABASE_URL`.

    Na komputerze to Postgres z docker compose. Na telefonie Postgresa nie ma
    (a stawianie go tam to demon, ktory zjada bateria), wiec baza jest jednym
    plikiem SQLite. Podanie `DATABASE_URL` przebija jedno i drugie - kto chce
    Postgresa w Termuxie, dostanie go bez zmiany kodu.
    """
    podany = os.environ.get("DATABASE_URL")
    if podany:
        return podany
    if czy_termux():
        SQLITE_TELEFON.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{SQLITE_TELEFON}"
    return POSTGRES_DOMYSLNY


def opcje_silnika(adres: str) -> dict:
    """Ustawienia puli polaczen - inne dla serwera, inne dla pliku.

    `pool_recycle` ma sens tam, gdzie polaczenie idzie po sieci i moze zostac
    zerwane po drodze. SQLite to plik: nie ma czego odswiezac, a `check_same_thread`
    trzeba wylaczyc, bo gunicorn obsluguje zadania w kilku watkach.
    """
    if adres.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False, "timeout": 30}}
    return {"pool_pre_ping": True, "pool_recycle": 300}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = domyslny_adres_bazy()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = opcje_silnika(SQLALCHEMY_DATABASE_URI)

    # Katalog z dokumentacja projektowa (PDF, XLSX, osnowa)
    DOCS_DIR = Path(os.environ.get("DOCS_DIR", BASE_DIR / "docs"))
    EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", BASE_DIR / "data" / "exports"))
    # Zdjecia z budowy leza POZA `exports`: tamto jest kasowalnym cache,
    # a wykop, ktory sfotografowano, zostanie zasypany i nie wroci.
    ZDJECIA_DIR = Path(os.environ.get("ZDJECIA_DIR", BASE_DIR / "data" / "zdjecia"))

    # Bez tego Flask przyjmuje pliki dowolnej wielkosci. Zdjecie z telefonu ma
    # kilkanascie megabajtow, wiec 25 MB zostawia zapas, a jednoczesnie nie
    # pozwala zapchac dysku jednym zadaniem.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", 25)) * 1024 * 1024

    # Domyslne pliki zrodlowe
    PROFILE_PDF = "Profile Scalone.pdf"
    MATERIAL_XLSX = "Materiał.xlsx"
    OSNOWA_TXT = "!!_DK29_osnowa_ok_v1.txt"

    # Uklad wspolrzednych osnowy geodezyjnej
    DEFAULT_CRS = "PL-2000/5"

    # Mozna wylaczyc tylko w testach; w normalnej pracy caly panel jest chroniony.
    WYMAGAJ_LOGOWANIA = os.environ.get("WYMAGAJ_LOGOWANIA", "1") != "0"
    REMEMBER_COOKIE_DAYS = int(os.environ.get("REMEMBER_COOKIE_DAYS", 14))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    JSON_AS_ASCII = False
    JSONIFY_PRETTYPRINT_REGULAR = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    return ProductionConfig if env.startswith("prod") else DevelopmentConfig
