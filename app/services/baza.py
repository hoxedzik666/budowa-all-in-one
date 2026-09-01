"""Ustawienia silnika bazy, ktore zalezą od tego, na czym on stoi.

Postgres w kontenerze i SQLite na telefonie to ta sama aplikacja, ale nie ta
sama baza. SQLite w ustawieniach fabrycznych zachowuje sie tak, ze na telefonie
szybko widac tego skutki:

* **Blokada calego pliku przy kazdym zapisie.** Domyslny dziennik (`journal_mode
  = DELETE`) wstrzymuje odczyty na czas zapisu. Gunicorn obsluguje kilka zadan
  naraz - brygadzista przewijajacy liste odcinkow potrafi wtedy dostac
  "database is locked" tylko dlatego, ze ktos w tym samym momencie zapisal
  pomiar. `WAL` rozdziela czytajacych od piszacego i problem znika.
* **Natychmiastowa rezygnacja przy zajetej bazie.** Domyslnie SQLite czeka zero
  sekund. Pamiec flash w telefonie bywa wolna, wiec dajemy 5 sekund - to nadal
  mniej, niz trwaloby tlumaczenie uzytkownikowi, czemu zapis "czasem nie wchodzi".
* **Wylaczone klucze obce.** SQLite sprawdza je tylko na zadanie, osobno dla
  kazdego polaczenia. Bez `PRAGMA foreign_keys=ON` baza na telefonie
  przyjmowalaby dane, ktore Postgres by odrzucil - a to jest gorsze niz blad,
  bo wychodzi dopiero przy scalaniu.

Pragmy ustawia sie **na kazdym polaczeniu z osobna**: SQLite nie ma
konfiguracji serwera, bo nie ma serwera.
"""
from __future__ import annotations

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

CZAS_OCZEKIWANIA_MS = 5000


def wlacz_pragmy_sqlite() -> None:
    """Wepnij nasluch ustawiajacy pragmy przy kazdym nowym polaczeniu SQLite.

    Rejestracja jest idempotentna - `create_app()` bywa wolane wielokrotnie
    (testy tworza aplikacje dla kazdego zestawu), a podpiete dwa razy nasluch
    ustawialby te same pragmy dwa razy.
    """
    if getattr(wlacz_pragmy_sqlite, "_wpiete", False):
        return

    @event.listens_for(Engine, "connect")
    def _ustaw_pragmy(polaczenie, _rekord):  # noqa: ANN001
        if not isinstance(polaczenie, sqlite3.Connection):
            return
        kursor = polaczenie.cursor()
        try:
            kursor.execute("PRAGMA journal_mode=WAL")
            kursor.execute("PRAGMA foreign_keys=ON")
            kursor.execute(f"PRAGMA busy_timeout={CZAS_OCZEKIWANIA_MS}")
        finally:
            kursor.close()

    wlacz_pragmy_sqlite._wpiete = True
