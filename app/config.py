"""Konfiguracja aplikacji."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://budowa:budowa@localhost:5433/budowa",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Katalog z dokumentacja projektowa (PDF, XLSX, osnowa)
    DOCS_DIR = Path(os.environ.get("DOCS_DIR", BASE_DIR / "docs"))
    EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", BASE_DIR / "data" / "exports"))

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
