"""Wspolne fixture dla testow.

Uwaga o kontekscie aplikacji
----------------------------
Flask NIE tworzy nowego kontekstu aplikacji dla zadania, jesli jakis kontekst
tej samej aplikacji jest juz aktywny. Gdyby wiec trzymac jeden kontekst przez
cala sesje testowa, obiekt `g` bylby wspolny dla wszystkich zadan - a Flask-Login
trzyma w `g._login_user` cache zalogowanej osoby. Efekt: klient "anonimowy"
dziedziczylby sesje po tescie, ktory sie zalogowal.

Dlatego kontekst jest **na kazdy test osobny**, a kazdy klient czysci ten cache
przed kazdym zadaniem. W normalnej pracy problem nie wystepuje, bo tam kazde
zadanie HTTP dostaje swiezy kontekst.

Czyszczenie dotyczy **wszystkich** klientow, nie tylko anonimowego. Test, ktory
uzywa dwoch roznych zalogowanych kont naraz (np. kierownik i monter), inaczej
wykonalby oba zadania jako ta osoba, ktora zalogowala sie pierwsza - i cicho
przepuscilby blad w uprawnieniach.
"""
import os
import tempfile
from pathlib import Path

import pytest
from flask import g
from flask.testing import FlaskClient


def _brak(nazwa: str) -> bool:
    """Czy biblioteki nie da sie zaimportowac - bez importowania jej.

    `find_spec` potrafi zglosic wyjatek (uszkodzona instalacja, podmieniony
    mechanizm importu), a nie tylko zwrocic None. Dla nas oba przypadki znacza
    to samo: nie ma na czym polegac.
    """
    from importlib.util import find_spec

    try:
        return find_spec(nazwa) is None
    except (ImportError, ValueError):
        return True


def _adres_bazy_testowej() -> str:
    """Na czym maja stanac testy.

    W kontenerze `DATABASE_URL` ustawia docker compose i to on wygrywa - testy
    ida wtedy po Postgresie, tak samo jak aplikacja w pracy.

    Poza kontenerem Postgresa moze nie byc wcale: na telefonie w Termuxie ani
    sterownika `psycopg`, ani serwera bazy nie da sie zainstalowac. Zamiast
    wywalac sie na polaczeniu, testy biegna wtedy po pliku SQLite - tym samym
    silniku, na ktorym stoi tam aplikacja.
    """
    podany = os.environ.get("DATABASE_URL")
    if podany:
        return podany

    if not _brak("psycopg"):
        return "postgresql+psycopg://budowa:budowa@db:5432/budowa"

    plik = Path(tempfile.gettempdir()) / "budowa-testy.sqlite3"
    return f"sqlite:///{plik}"


os.environ["DATABASE_URL"] = _adres_bazy_testowej()

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402

LOGIN_TESTOWY = "pytest-admin"
HASLO_TESTOWE = "pytest-haslo-testowe"


# Testy, ktore bez tych bibliotek nie maja czego sprawdzac. Na komputerze obie
# sa w `requirements.txt` i nic sie nie pomija; na telefonie (Termux) nie da sie
# ich zainstalowac - i wtedy pominiecie jest uczciwsze niz czerwony wynik, ktory
# nie mowi nic o kodzie.
wymaga_pymupdf = pytest.mark.skipif(
    _brak("fitz"), reason="PyMuPDF niedostepny (np. Termux) - nie ma czym czytac PDF")
wymaga_pyproj = pytest.mark.skipif(
    _brak("pyproj"), reason="pyproj niedostepny (np. Termux) - nie ma czym przeliczyc GPS")


class KlientZeSwiezymKontekstem(FlaskClient):
    """Klient, ktory przed kazdym zadaniem zapomina, kto byl zalogowany.

    Osoba zostaje wczytana na nowo z ciasteczka sesji tego klienta - dokladnie
    tak, jak dzieje sie przy prawdziwym zadaniu HTTP.
    """

    def open(self, *args, **kwargs):
        g.pop("_login_user", None)
        return super().open(*args, **kwargs)


@pytest.fixture(scope="session")
def app():
    aplikacja = create_app()
    aplikacja.test_client_class = KlientZeSwiezymKontekstem
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
    return app.test_client()


@pytest.fixture()
def db(app, kontekst_aplikacji):
    return _db


@pytest.fixture()
def wymaga_danych(db):
    """Test ma sens tylko na bazie z zaimportowana dokumentacja.

    Swieza instalacja - a taka jest kazda instalacja w Termuxie - ma baze pusta.
    Test, ktory szuka wtedy odcinka `Wyl101-D155`, nie mowi nic o kodzie, wiec
    zamiast czerwonego wyniku daje pominiecie ze wskazowka, czego brakuje.
    """
    from sqlalchemy import func, select

    from app.models import Segment

    # Swieza instalacja (telefon) nie ma jeszcze zadnej tabeli - bez tego
    # pytanie o liczbe odcinkow konczy sie bledem zamiast pominieciem.
    db.create_all()

    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip(
            "Baza pusta - uruchom 'flask import-wszystko' na komputerze "
            "albo wgraj zrzut (docs/project-docs/16-termux.md)."
        )
