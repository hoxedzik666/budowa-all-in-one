"""Wspolne fixture dla testow.

Uwaga o kontekscie aplikacji
----------------------------
Flask NIE tworzy nowego kontekstu aplikacji dla zadania, jesli jakis kontekst
tej samej aplikacji jest juz aktywny. Gdyby wiec trzymac jeden kontekst przez
cala sesje testowa, obiekt `g` bylby wspolny dla wszystkich zadan - a Flask-Login
trzyma w `g._login_user` cache zalogowanej osoby. Efekt: klient "anonimowy"
dziedziczylby sesje po tescie, ktory sie zalogowal.

Dlatego kontekst jest **na kazdy test osobny**, a klient anonimowy dodatkowo
czysci ten cache przed kazdym zadaniem. W normalnej pracy problem nie wystepuje,
bo tam kazde zadanie HTTP dostaje swiezy kontekst.
"""
import os

import pytest
from flask import g
from flask.testing import FlaskClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://budowa:budowa@db:5432/budowa")

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402

LOGIN_TESTOWY = "pytest-admin"
HASLO_TESTOWE = "pytest-haslo-testowe"


class KlientBezSesji(FlaskClient):
    """Klient, ktory przed kazdym zadaniem zapomina o zalogowanej osobie."""

    def open(self, *args, **kwargs):
        g.pop("_login_user", None)
        return super().open(*args, **kwargs)


@pytest.fixture(scope="session")
def app():
    aplikacja = create_app()
    yield aplikacja
    _usun_konto_testowe(aplikacja)


def _usun_konto_testowe(aplikacja):
    """Konto testowe ma haslo zapisane w repozytorium.

    Gdyby zostalo w bazie, kazdy kto widzi kod mialby konto administratora.
    """
    from sqlalchemy import delete, select

    with aplikacja.app_context():
        from app.models import Task, User

        konto = _db.session.scalar(select(User).where(User.login == LOGIN_TESTOWY))
        if konto is None:
            return
        _db.session.execute(delete(Task).where(Task.autor_id == konto.id))
        _db.session.delete(konto)
        _db.session.commit()


@pytest.fixture(autouse=True)
def kontekst_aplikacji(app):
    ctx = app.app_context()
    ctx.push()
    try:
        yield ctx
    finally:
        _db.session.remove()
        ctx.pop()


@pytest.fixture()
def konto_testowe(app, kontekst_aplikacji):
    """Konto administratora uzywane przez testy HTTP."""
    from sqlalchemy import func, select

    from app.models import Rola, User

    _db.create_all()
    uzytkownik = _db.session.scalar(
        select(User).where(func.lower(User.login) == LOGIN_TESTOWY)
    )
    if uzytkownik is None:
        uzytkownik = User(login=LOGIN_TESTOWY, imie_nazwisko="Konto testowe")
        _db.session.add(uzytkownik)
    uzytkownik.rola = Rola.ADMIN
    uzytkownik.aktywny = True
    uzytkownik.ustaw_haslo(HASLO_TESTOWE)
    _db.session.commit()
    return uzytkownik


@pytest.fixture()
def klient(app, konto_testowe):
    """Zalogowany klient - domyslny dla wiekszosci testow."""
    c = app.test_client()
    odpowiedz = c.post("/login", data={"login": LOGIN_TESTOWY, "haslo": HASLO_TESTOWE})
    assert odpowiedz.status_code == 302, "Nie udalo sie zalogowac konta testowego"
    return c


@pytest.fixture()
def klient_anonim(app, konto_testowe):
    """Klient bez sesji - do sprawdzania, czy ochrona faktycznie dziala."""
    app.test_client_class = KlientBezSesji
    try:
        return app.test_client()
    finally:
        app.test_client_class = None


@pytest.fixture()
def db(app, kontekst_aplikacji):
    return _db
