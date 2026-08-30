"""Fabryka aplikacji Flask."""
import json
from decimal import Decimal

from flask import Flask, redirect, request, url_for
from flask.json.provider import DefaultJSONProvider
from flask_login import current_user

from app.config import get_config
from app.extensions import db, login_manager, migrate


class PolishJSONProvider(DefaultJSONProvider):
    """Nie escapuj polskich znakow i serializuj Decimal jako liczbe."""

    ensure_ascii = False
    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app(config_object=None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object or get_config())
    app.json = PolishJSONProvider(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.zaloguj"
    login_manager.login_message = "Zaloguj się, żeby korzystać z narzędzia."
    login_manager.login_message_category = "info"

    # Import modeli musi nastapic przed create_all / migracjami.
    from app import models  # noqa: F401
    from app.models import User

    @login_manager.user_loader
    def wczytaj_uzytkownika(uid: str):
        return db.session.get(User, int(uid))

    from app.blueprints.api import api_bp
    from app.blueprints.auth import auth_bp, czy_wymaga_logowania
    from app.blueprints.main import main_bp
    from app.blueprints.mapa import mapa_bp
    from app.blueprints.niwelator import niwelator_bp
    from app.blueprints.panel import panel_bp
    from app.blueprints.postep import postep_bp
    from app.blueprints.pwa import pwa_bp
    from app.blueprints.szukaj import szukaj_bp
    from app.blueprints.wykonanie import wykonanie_bp
    from app.blueprints.zadania import zadania_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(niwelator_bp, url_prefix="/niwelator")
    app.register_blueprint(szukaj_bp)
    app.register_blueprint(mapa_bp)
    app.register_blueprint(panel_bp)
    app.register_blueprint(zadania_bp)
    app.register_blueprint(wykonanie_bp)
    app.register_blueprint(pwa_bp)
    app.register_blueprint(postep_bp)

    @app.before_request
    def wymagaj_logowania():
        """Cala aplikacja jest za logowaniem - to narzedzie konkretnej budowy."""
        if not app.config.get("WYMAGAJ_LOGOWANIA", True):
            return None
        if current_user.is_authenticated:
            return None
        if not czy_wymaga_logowania(request.endpoint):
            return None
        return redirect(url_for("auth.zaloguj", next=request.full_path.rstrip("?")))

    from app.cli import register_cli

    register_cli(app)

    # Slowniki stanow rejestrujemy jako globalne Jinjy, a nie przez
    # context_processor: makra (np. karta odcinka) nie widza kontekstu
    # szablonu, ktory je wywolal, ale globalne widza zawsze.
    from app.models import ETYKIETY as _etykiety_stanu
    from app.models import KLASY_PLAKIETKI as _klasy_stanu
    from app.models import SCIEZKA as _sciezka_robot

    # `current_user` z Flask-Login jest zwyklym context processorem, wiec makro
    # (importowane bez kontekstu) go nie widzi - a karta odcinka pyta o
    # uprawnienia. LocalProxy rozwiazuje sie przy odczycie, wiec ten sam obiekt
    # dziala jako globalna Jinjy.
    app.jinja_env.globals.update(
        current_user=current_user,
        stany_robot=list(_sciezka_robot),
        etykiety_stanu=_etykiety_stanu,
        klasy_stanu=_klasy_stanu,
    )

    @app.template_filter("liczba")
    def _liczba(value, miejsca: int = 2):
        if value is None:
            return "—"
        return f"{float(value):.{miejsca}f}".replace(".", ",")

    @app.template_filter("tojson_pl")
    def _tojson_pl(value):
        return json.dumps(value, ensure_ascii=False, default=str)

    @app.context_processor
    def _wspolne_dla_szablonow():
        """Licznik zadan w pasku nawigacji - potrzebny na kazdej stronie."""
        if not current_user.is_authenticated:
            return {"otwarte_zadania": 0}
        from app.blueprints.zadania import licz_otwarte

        try:
            return {"otwarte_zadania": licz_otwarte(current_user)}
        except Exception:  # noqa: BLE001 - brak tabeli przed init-db nie moze psuc widoku
            db.session.rollback()
            return {"otwarte_zadania": 0}

    @app.shell_context_processor
    def _shell():
        from app.models import (
            NetworkObject,
            Profile,
            Segment,
            Sheet,
            SurveyPoint,
            Task,
            User,
        )

        return {
            "db": db,
            "Profile": Profile,
            "NetworkObject": NetworkObject,
            "Segment": Segment,
            "Sheet": Sheet,
            "SurveyPoint": SurveyPoint,
            "User": User,
            "Task": Task,
        }

    return app
