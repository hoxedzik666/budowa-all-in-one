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

Dwa silniki, dwie sciezki
-------------------------
Na komputerze baza stoi na Postgresie, na telefonie - na SQLite (jeden plik,
bez demona). Prawie wszystko, co robi ten modul, jest w tych silnikach opisane
inna skladnia:

|                          | Postgres                     | SQLite                      |
|--------------------------|------------------------------|-----------------------------|
| czy tabela istnieje      | `to_regclass`                | inspektor SQLAlchemy        |
| dolozenie kolumny        | `ADD COLUMN IF NOT EXISTS`   | brak `IF NOT EXISTS` -      |
|                          |                              | najpierw pytamy inspektora  |
| wartosc w typie enum     | `ALTER TYPE ... ADD VALUE`   | nie dotyczy (patrz nizej)   |
| przyciecie tekstu        | `left(x, 120)`               | `substr(x, 1, 120)`         |
| kasowanie duplikatow     | `DELETE ... USING`           | `DELETE ... WHERE id NOT IN`|

Typow wyliczeniowych w SQLite nie ma w ogole: `Enum` staje sie tam `VARCHAR`
z warunkiem `CHECK`, budowanym przy tworzeniu tabeli z **aktualnej** listy
wartosci w Pythonie. Nowa rola jest wiec w bazie od razu - nie ma czego dokladac.
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.extensions import db

# Kolumny dokladane do tabel, ktore juz istnieja. Typ podany osobno dla kazdego
# silnika, bo SQLite nie zna `FALSE` jako wartosci domyslnej dla BOOLEAN.
KOLUMNY: list[tuple[str, str, str, str]] = [
    ("segment", "podejrzany", "BOOLEAN NOT NULL DEFAULT FALSE", "BOOLEAN NOT NULL DEFAULT 0"),
    ("segment", "powod_podejrzenia", "TEXT", "TEXT"),
]

INDEKSY: list[tuple[str, str]] = [
    ("ix_segment_podejrzany", "CREATE INDEX IF NOT EXISTS ix_segment_podejrzany "
                              "ON segment (podejrzany)"),
    ("ix_segment_status", "CREATE INDEX IF NOT EXISTS ix_segment_status "
                          "ON segment (status)"),
]

# Nowe wartosci w istniejacych typach wyliczeniowych. `create_all` tworzy typ
# raz i nigdy go nie rusza, wiec dopisanie roli w Pythonie nie dolozy jej
# w bazie - przy pierwszym zapisie wyszedlby blad "invalid input value for enum".
#
# UWAGA: `ALTER TYPE ... ADD VALUE` jest **nieodwracalny** - Postgres nie ma
# `DROP VALUE`. Literowka oznacza przebudowe typu, wiec kazda pozycja tej listy
# powinna byc przeczytana dwa razy. (Na SQLite ta lista nic nie robi.)
WARTOSCI_ENUM: list[tuple[str, str]] = [
    ("rola", "MONTER"),
]

# Naturalny klucz polaczenia. `opis` przycinamy do 120 znakow, bo indeks btree
# ma ograniczenie dlugosci wpisu, a `coalesce` jest konieczne, bo w Postgresie
# dwa NULL-e sa dla indeksu unikalnego rozne - bez tego duplikaty z pustym
# kodem zrodlowym przeszlyby bokiem.
def _kolumny_klucza(przytnij: str) -> str:
    return f"""
    obiekt_id,
    coalesce(obiekt_zrodlowy_kod, ''),
    coalesce(dn_mm, -1),
    coalesce(rzedna, -9999),
    kierunek,
    {przytnij}
"""


PRZYTNIJ_OPIS = {
    "postgresql": "left(coalesce(opis, ''), 120)",
    "sqlite": "substr(coalesce(opis, ''), 1, 120)",
}

# Zostawia najstarszy wiersz z kazdej grupy identycznych polaczen.
ODSIEJ_DUPLIKATY_PG = """
DELETE FROM connection c USING connection starszy
WHERE c.id > starszy.id
  AND c.obiekt_id = starszy.obiekt_id
  AND coalesce(c.obiekt_zrodlowy_kod, '') = coalesce(starszy.obiekt_zrodlowy_kod, '')
  AND coalesce(c.dn_mm, -1) = coalesce(starszy.dn_mm, -1)
  AND coalesce(c.rzedna, -9999) = coalesce(starszy.rzedna, -9999)
  AND c.kierunek = starszy.kierunek
  AND left(coalesce(c.opis, ''), 120) = left(coalesce(starszy.opis, ''), 120)
"""

# To samo dla SQLite, ktory nie zna `USING`: grupujemy po tym samym kluczu
# naturalnym i zostawiamy najmniejszy identyfikator z kazdej grupy.
ODSIEJ_DUPLIKATY_SQLITE = f"""
DELETE FROM connection
WHERE id NOT IN (
    SELECT MIN(id) FROM connection
    GROUP BY {_kolumny_klucza(PRZYTNIJ_OPIS["sqlite"])}
)
"""


def _dialekt() -> str:
    return db.engine.dialect.name


def _tabela_istnieje(nazwa: str) -> bool:
    if _dialekt() == "postgresql":
        return bool(db.session.scalar(text("SELECT to_regclass(:n)"), {"n": nazwa}))
    return inspect(db.engine).has_table(nazwa)


def _kolumna_istnieje(tabela: str, kolumna: str) -> bool:
    return any(k["name"] == kolumna for k in inspect(db.engine).get_columns(tabela))


def _typ_istnieje(nazwa: str) -> bool:
    return bool(db.session.scalar(
        text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": nazwa}))


def _ma_wartosc(typ: str, wartosc: str) -> bool:
    return bool(db.session.scalar(
        text("SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
             "WHERE t.typname = :t AND e.enumlabel = :w"),
        {"t": typ, "w": wartosc},
    ))


def _dopisz_wartosci_enum() -> list[str]:
    """Dopisz brakujace wartosci do istniejacych typow wyliczeniowych.

    `ALTER TYPE ... ADD VALUE` nie da sie wykonac wewnatrz transakcji, ktora
    tego typu potem uzywa, wiec kazda zmiana idzie osobnym polaczeniem
    z autocommitem.

    Tylko Postgres - SQLite nie ma typow wyliczeniowych (patrz naglowek modulu).
    """
    if _dialekt() != "postgresql":
        return []
    wykonane: list[str] = []
    for typ, wartosc in WARTOSCI_ENUM:
        if not _typ_istnieje(typ) or _ma_wartosc(typ, wartosc):
            continue
        with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as pol:
            pol.execute(text(f"ALTER TYPE {typ} ADD VALUE IF NOT EXISTS '{wartosc}'"))
        wykonane.append(f"{typ} += {wartosc}")
    return wykonane


def _doloz_kolumny() -> list[str]:
    postgres = _dialekt() == "postgresql"
    wykonane: list[str] = []
    for tabela, kolumna, typ_pg, typ_sqlite in KOLUMNY:
        if not _tabela_istnieje(tabela):
            continue
        if postgres:
            db.session.execute(
                text(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {kolumna} {typ_pg}")
            )
        else:
            # SQLite nie zna `IF NOT EXISTS` przy kolumnie i konczy sie bledem,
            # gdy kolumna juz jest - wiec pytamy najpierw.
            if _kolumna_istnieje(tabela, kolumna):
                continue
            db.session.execute(
                text(f"ALTER TABLE {tabela} ADD COLUMN {kolumna} {typ_sqlite}")
            )
        wykonane.append(f"{tabela}.{kolumna}")
    return wykonane


def _uporzadkuj_polaczenia() -> list[str]:
    """Odsiej zdublowane polaczenia i zaloz na nie indeks unikalny.

    Powod calej operacji opisuje docs/project-docs/11-audyt-danych.md: import
    uruchomiony dwa razy dokladal te same wiersze zamiast je rozpoznac.
    """
    if not _tabela_istnieje("connection"):
        return []
    dialekt = _dialekt()
    odsiej = ODSIEJ_DUPLIKATY_PG if dialekt == "postgresql" else ODSIEJ_DUPLIKATY_SQLITE
    przytnij = PRZYTNIJ_OPIS.get(dialekt, PRZYTNIJ_OPIS["sqlite"])

    wykonane: list[str] = []
    usuniete = db.session.execute(text(odsiej)).rowcount or 0
    if usuniete:
        wykonane.append(f"odsiano {usuniete} zdublowanych polaczen")
    db.session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_naturalny ON connection ("
        + _kolumny_klucza(przytnij) + ")"
    ))
    wykonane.append("uq_connection_naturalny")
    return wykonane


def dostosuj_schemat() -> list[str]:
    """Dolóż brakujace kolumny, indeksy i wartosci enumow.

    Zwraca liste wykonanych zmian.
    """
    wykonane: list[str] = _dopisz_wartosci_enum()
    wykonane += _doloz_kolumny()

    for nazwa, polecenie in INDEKSY:
        if not _tabela_istnieje(polecenie.split(" ON ")[1].split(" ")[0]):
            continue
        db.session.execute(text(polecenie))
        wykonane.append(nazwa)

    wykonane += _uporzadkuj_polaczenia()

    db.session.commit()
    return wykonane
