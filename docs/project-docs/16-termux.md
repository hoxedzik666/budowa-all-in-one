# Serwer na telefonie — Termux

> Stan: **działa**. Etap 7.
>
> [`13-android-apk.md`](13-android-apk.md) postawił tezę: „APK będzie klientem,
> nie kopią aplikacji", bo *„PostgreSQL 16 — brak sensownego portu na Androida"*
> i *„PyMuPDF — biblioteka natywna"*. Teza była słuszna co do **PyMuPDF**
> i przedwczesna co do **bazy**: kanalizacja to graf, ale wszystkie zapytania
> w tym projekcie to zwykłe złączenia po kluczach — a takie SQLite liczy
> bez zająknięcia. Ten dokument opisuje, co z tego wyszło.

Całe narzędzie da się uruchomić **na telefonie**, w [Termuxie](https://termux.dev):
Flask, baza i serwer stoją w kieszeni, a otwiera się je przeglądarką pod
`http://127.0.0.1:8000` albo aplikacją z `.apk/`, wskazaną na ten sam adres.

Po co: na budowie nie zawsze jest komputer i nie zawsze jest Wi-Fi. Serwer
w telefonie działa również w trybie samolotowym — pętla zwrotna nie potrzebuje
żadnej sieci.

---

## Instalacja

```bash
pkg install git
git clone <adres-repozytorium> ~/budowa-all-in-one
cd ~/budowa-all-in-one
./termux/instaluj.sh
```

Skrypt instaluje paczki Termuxa i biblioteki Pythona, tworzy `.env`
z wylosowanym `SECRET_KEY`, zakłada bazę i konto administratora (hasło wypisuje
raz na ekranie). Można go puszczać wielokrotnie — niczego nie kasuje.

```bash
./termux/uruchom.sh          # serwer tylko dla tego telefonu
./termux/uruchom.sh --siec   # widoczny też dla reszty brygady przez Wi-Fi
```

Zatrzymanie: `Ctrl+C`. Termux musi zostać uruchomiony — serwer żyje tak długo
jak on.

---

## Skąd biorą się dane

Baza po instalacji jest **pusta**. Niwelator, zadania i raporty dzienne działają
od razu, bo nie potrzebują dokumentacji. Reszta — odcinki, rzędne, materiały —
pochodzi z importu, a importu telefon nie wykona: czyta on PDF-y przez PyMuPDF,
którego na Androidzie nie ma (patrz niżej).

Dlatego dane przygotowuje komputer i przekazuje jednym plikiem:

```bash
# na komputerze, przy działającym docker compose:
docker compose exec web python -m flask zrzut-sqlite
#   → data/exports/budowa-telefon.sqlite3
```

Komenda przepisuje wszystkie tabele do pliku SQLite — łącznie z kontami,
raportami i historią stanów. Plik przegrywa się na telefon (kabel, chmura,
pendrive) jako:

```
~/budowa-all-in-one/data/budowa.sqlite3
```

Po podmianie wystarczy uruchomić serwer ponownie.

> **Przeniesienie w drugą stronę** (pomiary z telefonu z powrotem na serwer) nie
> jest zrobione. Telefon i komputer to na razie dwie osobne bazy — zlanie ich
> w jedną wymaga rozstrzygnięcia, co ma wygrać przy sprzecznych zapisach,
> a to jest osobna decyzja, nie szczegół techniczny.

---

## W przeglądarce

Otwórz w Chrome (albo Firefoksie) `http://127.0.0.1:8000` i zaloguj się kontem
z instalacji.

**Aplikację da się zainstalować na ekranie startowym** — menu przeglądarki →
*Dodaj do ekranu głównego*. Service worker działa, mimo że nie ma HTTPS:
przeglądarki traktują `127.0.0.1` jako **kontekst zaufany**, dokładnie po to,
żeby dało się rozwijać lokalnie. Ikonę i manifest dostarcza `pwa.py`, ten sam,
który obsługuje instalację z serwera na budowie.

Aparat i lokalizacja z poziomu przeglądarki działają z tego samego powodu —
przeglądarka nie odmawia dostępu na localhoście.

---

## W aplikacji (APK)

APK z katalogu `.apk/` jest powłoką, która pokazuje stronę z serwera. Serwerem
może być ten sam telefon:

1. Uruchom Termuxa i `./termux/uruchom.sh`.
2. Otwórz aplikację → **Serwer na tym telefonie (Termux)**.
3. Aplikacja sprawdza połączenie i zapamiętuje adres `http://127.0.0.1:8000`.

Adres zmienia się w menu konta → *Zmień adres serwera*, więc ten sam APK
obsługuje oba tryby: serwer w kieszeni i serwer na budowie.

Gdy przy uruchomieniu serwer nie odpowiada (najczęściej: Termux nie został
włączony), aplikacja pokazuje ekran `web/blad.html` z komendą do wpisania —
zamiast białej strony bez wyjaśnienia. Odpowiada za to `server.errorPath`
w `capacitor.config.json`.

---

## Czego nie ma na telefonie i dlaczego

**PyMuPDF się nie zainstaluje.** Termux to Android, czyli bionic libc — koła
z PyPI budowane dla Linuksa (manylinux) tam nie wchodzą, a budowa ze źródeł
oznacza skompilowanie całego MuPDF. `./termux/instaluj.sh --z-pdf` próbuje,
odnotowuje wynik i idzie dalej.

Bez PyMuPDF nie działają: **mapa planów i kafelki**, **wycinki oryginału PDF**
oraz **import dokumentacji**. Te trzy rzeczy pokazują stronę z wyjaśnieniem
i kodem **503** — nie błąd 500, bo program jest sprawny, tylko tej jednej rzeczy
tutaj nie zrobi.

Działa cała reszta: wyszukiwarka, karty odcinków, przelicznik rur, niwelator,
tyczenie ciągu, materiały, postęp robót, raporty dzienne, zadania, kody QR
i zdjęcia z budowy.

Osobno: **`pyproj`** (przeliczenie GPS na PL-2000/5) wymaga biblioteki PROJ.
Da się doinstalować: `pkg install proj && pip install pyproj`.

Mechanizm opisuje `app/services/opcjonalne.py`: `import fitz` zamieniony jest na
leniwy odpowiednik, więc brak biblioteki przewraca **jedną funkcję**, a nie
całą aplikację. Wcześniej `import fitz` stał na poziomie modułu w blueprintcie
mapy — i bez PyMuPDF nie dało się otworzyć nawet niwelatora.

---

## Baza: SQLite zamiast Postgresa

Adres bazy wybiera `app/config.py`: `DATABASE_URL` z otoczenia ma pierwszeństwo,
a gdy go nie ma — Postgres na komputerze, plik SQLite w Termuxie (rozpoznanym
po `TERMUX_VERSION`/`PREFIX`).

Co trzeba było uzgodnić między silnikami:

| Rzecz | Postgres | SQLite |
|---|---|---|
| `JSONB` w modelach | zostaje `JSONB` | zwykły `JSON` |
| typy wyliczeniowe | `ALTER TYPE … ADD VALUE` | `VARCHAR` + `CHECK`, nic do robienia |
| `ADD COLUMN IF NOT EXISTS` | jest | najpierw pytamy inspektora |
| `left(x, 120)` | jest | `substr(x, 1, 120)` |
| `DELETE … USING` | jest | `DELETE … WHERE id NOT IN (…)` |

Kolumny JSON deklaruje `app/models/typy.py` jako `JSON` z **wariantem** `JSONB`
dla Postgresa. Dzięki temu DDL po stronie Postgresa **nie zmienia się wcale** —
działające bazy nie wymagają migracji. Resztę różnic obsługuje
`app/services/schemat.py`, rozgałęziony po dialekcie.

Trzy pragmy ustawiane przy każdym połączeniu SQLite (`app/services/baza.py`)
nie są ozdobą:

- **`journal_mode=WAL`** — bez niego zapis blokuje odczyty. Przy kilku wątkach
  gunicorna przeglądanie listy odcinków potrafiło się wywalić na „database is
  locked" tylko dlatego, że ktoś w tej samej chwili zapisał pomiar.
- **`busy_timeout=5000`** — pamięć flash w telefonie bywa wolna, a fabrycznie
  SQLite nie czeka ani chwili.
- **`foreign_keys=ON`** — SQLite sprawdza klucze obce dopiero na żądanie.
  Bez tego telefon przyjmowałby dane, które Postgres by odrzucił, i wyszłoby to
  dopiero przy scalaniu.

### Wariant z Postgresem w Termuxie

Kto woli mieć jeden silnik wszędzie:

```bash
pkg install postgresql
pip install psycopg          # bez [binary] - kola dla Androida nie ma
initdb ~/pgdata && pg_ctl -D ~/pgdata start
createuser --superuser budowa && createdb -O budowa budowa
# w .env:
DATABASE_URL=postgresql+psycopg://budowa@127.0.0.1:5432/budowa
```

Działa, ale to demon do pilnowania i zauważalnie więcej baterii. Dane przenosi
się wtedy zwykłym `pg_dump`/`psql`, bez `zrzut-sqlite`.

---

## Bateria i autostart

`uruchom.sh` bierze `termux-wake-lock` i oddaje go przy wyjściu. Bez rygla
Android usypia proces — zwykle w połowie zapisu, więc objawia się to
„zawieszeniem" przy wysyłaniu raportu, a nie czytelnym błędem.

Serwer bez ruchu praktycznie nie zużywa prądu; koszt bierze się z ekranu
i z samego czuwania. Na dzień pracy w terenie to rząd kilku procent baterii.

Autostart przy włączeniu telefonu (opcjonalnie, wymaga dodatku Termux:Boot):

```bash
mkdir -p ~/.termux/boot
ln -s ~/budowa-all-in-one/termux/autostart.sh ~/.termux/boot/budowa
```

---

## Testy na telefonie

```bash
python -m pytest tests/test_termux.py -q     # sprawdzenie instalacji
python -m pytest -q                          # cala zbiorka
```

Pełna zbiórka przechodzi także na pustej bazie bez PyMuPDF: testy, które
potrzebują zaimportowanej dokumentacji albo bibliotek do PDF-ów, **pomijają
się** z wyjaśnieniem, zamiast świecić na czerwono. Czerwony wynik na telefonie
oznacza więc prawdziwy problem, a nie brak danych.

---

## Bezpieczeństwo

Domyślnie serwer słucha **tylko na `127.0.0.1`** — z zewnątrz jest niewidoczny,
nawet w tej samej sieci Wi-Fi. `--siec` to świadoma decyzja: wtedy hasło leci
po sieci otwartym tekstem (jak w wariancie z serwerem na budowie — patrz uwaga
w `network_security_config.xml`). W sieci budowy to przyjęty kompromis;
w kawiarnianym Wi-Fi lepiej bez tego.

Baza to jeden plik w katalogu domowym Termuxa, dostępny tylko dla tej aplikacji.
Zgubiony telefon oznacza jednak zgubione dane budowy — warto o tym pamiętać,
zanim wgra się tam pełny zrzut.
