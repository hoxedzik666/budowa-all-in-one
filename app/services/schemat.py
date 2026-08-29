"""Dostosowanie istniejacej bazy do zmian w modelach.

Dlaczego to istnieje
--------------------
Projekt zaklada schemat przez `db.create_all()`. To wygodne przy starcie, ale
`create_all` **tworzy tylko brakujace tabele - nie dotyka istniejacych**. Nowa
kolumna w modelu nie pojawi sie w bazie, ktora juz dziala, i wychodzi to dopiero
przy pierwszym zapytaniu, komunikatem "column does not exist".

Zamiast kasowac baze przy kazdej zmianie (a razem z nia recznie wskazane pozycje
na planach) trzymamy tu krotka liste zmian **addytywnych**, wykonywanych przy
kazdym `flask init-db`. Kazda z nich musi byc idempotentna - komenda leci przy
starcie kontenera.

Czego tu NIE robimy: kasowania kolumn i zmian typow. To sa zmiany, ktore moga
zniszczyc dane, i takie ida przez Flask-Migrate ze swiadoma decyzja czlowieka.
"""
from __future__ import annotations

from sqlalchemy import text

from app.extensions import db

# Kolumny dokladane do tabel, ktore juz istnieja. Postgres zna
# ADD COLUMN IF NOT EXISTS, wiec powtorzenie nic nie kosztuje.
KOLUMNY: list[tuple[str, str, str]] = [
    ("segment", "podejrzany", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("segment", "powod_podejrzenia", "TEXT"),
]

INDEKSY: list[tuple[str, str]] = [
    ("ix_segment_podejrzany", "CREATE INDEX IF NOT EXISTS ix_segment_podejrzany "
                              "ON segment (podejrzany)"),
]

# Naturalny klucz polaczenia. `opis` przycinamy do 120 znakow, bo indeks btree
# ma ograniczenie dlugosci wpisu, a `coalesce` jest konieczne, bo w Postgresie
# dwa NULL-e sa dla indeksu unikalnego rozne - bez tego duplikaty z pustym
# kodem zrodlowym przeszlyby bokiem.
INDEKS_POLACZEN = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_naturalny ON connection (
    obiekt_id,
    coalesce(obiekt_zrodlowy_kod, ''),
    coalesce(dn_mm, -1),
    coalesce(rzedna, -9999),
    kierunek,
    left(coalesce(opis, ''), 120)
)
"""

# Zostawia najstarszy wiersz z kazdej grupy identycznych polaczen.
ODSIEJ_DUPLIKATY = """
DELETE FROM connection c USING connection starszy
WHERE c.id > starszy.id
  AND c.obiekt_id = starszy.obiekt_id
  AND coalesce(c.obiekt_zrodlowy_kod, '') = coalesce(starszy.obiekt_zrodlowy_kod, '')
  AND coalesce(c.dn_mm, -1) = coalesce(starszy.dn_mm, -1)
  AND coalesce(c.rzedna, -9999) = coalesce(starszy.rzedna, -9999)
  AND c.kierunek = starszy.kierunek
  AND left(coalesce(c.opis, ''), 120) = left(coalesce(starszy.opis, ''), 120)
"""


def _tabela_istnieje(nazwa: str) -> bool:
    return bool(db.session.scalar(text("SELECT to_regclass(:n)"), {"n": nazwa}))


def dostosuj_schemat() -> list[str]:
    """Dolóż brakujace kolumny i indeksy. Zwraca liste wykonanych zmian."""
    wykonane: list[str] = []

    for tabela, kolumna, typ in KOLUMNY:
        if not _tabela_istnieje(tabela):
            continue
        db.session.execute(
            text(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {kolumna} {typ}")
        )
        wykonane.append(f"{tabela}.{kolumna}")

    for nazwa, polecenie in INDEKSY:
        if not _tabela_istnieje(polecenie.split(" ON ")[1].split(" ")[0]):
            continue
        db.session.execute(text(polecenie))
        wykonane.append(nazwa)

    if _tabela_istnieje("connection"):
        usuniete = db.session.execute(text(ODSIEJ_DUPLIKATY)).rowcount or 0
        if usuniete:
            wykonane.append(f"odsiano {usuniete} zdublowanych polaczen")
        db.session.execute(text(INDEKS_POLACZEN))
        wykonane.append("uq_connection_naturalny")

    db.session.commit()
    return wykonane
