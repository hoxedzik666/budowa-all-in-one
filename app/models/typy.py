"""Typy kolumn, ktore musza dzialac na dwoch silnikach naraz.

Baza stoi albo na Postgresie (komputer, docker compose), albo na SQLite
(telefon w Termuxie). Modele sa jedne.

`JSONB` istnieje wylacznie w Postgresie - kolumna zadeklarowana wprost tym
typem wywala sie na SQLite juz przy tworzeniu tabel. `with_variant` rozwiazuje
to bez rozgalezien w modelach: SQLAlchemy uzywa `JSONB` tam, gdzie dialektem
jest Postgres, a zwyklego `JSON` wszedzie indziej.

Dlaczego akurat w te strone, a nie odwrotnie: `JSONB` na Postgresie zostaje
**bez zmiany DDL**, wiec dzialajace bazy nie wymagaja ani migracji, ani
przebudowy kolumn. Po stronie Pythona nic sie nie zmienia - w obu wypadkach
odczytujemy i zapisujemy zwykle listy i slowniki.

Czego to NIE daje: zapytan po wnetrzu dokumentu (`->>`, indeksy GIN). Takich
w projekcie nie ma - kolumny `surowe` i `ostrzezenia` czytamy w calosci, po
kluczu glownym wiersza.
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSON_ELASTYCZNY = JSON().with_variant(JSONB(), "postgresql")
