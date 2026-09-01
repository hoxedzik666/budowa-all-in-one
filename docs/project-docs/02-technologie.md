# Technologie i uzasadnienie wyborów

---

## Stos

| Warstwa | Wybór | Wersja |
|---|---|---|
| Backend | Flask | 3.0.3 |
| ORM | SQLAlchemy (styl 2.0) + Flask-SQLAlchemy | 2.0.36 / 3.1.1 |
| Baza | PostgreSQL (na telefonie: SQLite) | 16-alpine |
| Serwer | gunicorn | 23.0.0 |
| Odczyt PDF | PyMuPDF (`fitz`) | 1.24.14 |
| Odczyt XLSX | openpyxl | 3.1.5 |
| OCR | tesseract + pytesseract | 5.5.0 / 0.3.13 |
| Front | Bootstrap 5.3.3 + Tailwind 3.4 + jQuery 3.7.1 | lokalnie |
| Konteneryzacja | Docker Compose | — |
| Testy | pytest | 8.3.4 |

---

## Dlaczego PostgreSQL

- **Sieć kanalizacyjna to graf.** Pytanie „co spływa do `Wyl101`?” to przejście
  grafu w górę zlewni — w Postgresie jedno `WITH RECURSIVE`.
- **`NUMERIC`, nie `float`.** Rzędne to setne części metra i muszą się sumować
  bez dryfu. Wszystkie rzędne: `NUMERIC(8,3)`.
- **`JSONB`** na surowy odczyt z parsera i listę ostrzeżeń importu — pozwala
  odpowiedzieć „skąd wzięła się ta liczba” bez wracania do PDF-u, a przy tym
  jest indeksowalny.
- **PostGIS** czeka gotowy, gdy pojawią się współrzędne obiektów.

## Dlaczego mimo to SQLite na telefonie

Na Androidzie (Termux) Postgres to demon do pilnowania i kilkadziesiąt megabajtów
w tle — a sterownik `psycopg` nie ma tam gotowego koła. SQLite jest jednym
plikiem, który da się przegrać kablem, i nie potrzebuje niczego uruchamiać.

Kosztu prawie nie ma, bo **żadne zapytanie w tym projekcie nie korzysta z tego,
co Postgres ma ponad SQLite**: `WITH RECURSIVE` na razie nie jest używane
(przejścia po grafie robimy w Pythonie), a kolumny JSON czytamy w całości, po
kluczu wiersza — nie po wnętrzu dokumentu. Zostaje `NUMERIC`, które SQLite
przyjmuje jako `NUMERIC` i zwraca przez `Decimal` po stronie SQLAlchemy.

Wybór jest jedną linijką: `DATABASE_URL` przebija automatykę, więc kto chce
Postgresa w Termuxie, nie musi ruszać kodu. Różnice składni między silnikami
siedzą w dwóch miejscach — `app/models/typy.py` (wariant `JSONB`) i
`app/services/schemat.py` (rozgałęzienie po dialekcie). Opis:
[`16-termux.md`](16-termux.md).

## Dlaczego PyMuPDF, a nie pdftotext

Profile mają fonty `Type0`/`CIDFontType2` z poprawnymi mapami `ToUnicode`.
PyMuPDF czyta z nich polskie znaki, `Ø` i `°` bezbłędnie oraz **podaje bbox
i orientację każdego spanu** — bez tego nie da się rozdzielić danych węzła
(pisanych pionowo) od danych odcinka (poziomych).

`pdftotext` z pakietu xpdf gubi diakrytykę bez `-enc UTF-8` i **nie ma trybu
współrzędnych**. Ręczne parsowanie strumienia treści też odpada — tekst siedzi
w Form XObjectach i transformacjach `cm`; próbne parsowanie wyciągnęło 1246
z ~190 000 znaków strony.

## Dlaczego front-end zwendorowany lokalnie

Bootstrap, Tailwind i jQuery leżą w `app/static/vendor/`, nie na CDN.
**Na budowie bywa bez zasięgu**, a narzędzie ma działać na telefonie
w wykopie tak samo jak w biurze.

Podział ról: **Bootstrap** — komponenty, tabele, modale, siatka;
**Tailwind** — klasy narzędziowe do gęstych widoków; **jQuery** — AJAX do API
i drobna interakcja (podpowiedzi, filtrowanie tabel, wskazywanie na mapie).

## Dlaczego serwisy nie znają Flaska

`rury.py` i `leveling.py` to czysta logika — dają się testować bez aplikacji
i bez bazy. Dzięki temu `tests/test_rury.py` (21 testów) i
`tests/test_niwelacja.py` (13 testów) biegną w ułamku sekundy i nie wymagają
Postgresa.

---

## Model danych

```
sheet ──< profile ──< object_occurrence >── network_object ──< connection
                 └──< segment >───────────┘                └──< plan_location
plan_sheet ──< plan_location
survey_point        material_item        import_run
```

Dwie decyzje warte odnotowania:

**`object_occurrence` jest osobną tabelą**, bo studnia ma tyle rzędnych dna, ile
wchodzi do niej rur — a każdy profil pokazuje „swoją”. Kanoniczna w
`network_object` jest **najniższa** (rzędna odpływu), reszta zostaje przy
wystąpieniach. Nic nie ginie, a widok obiektu pokazuje jednoznaczną liczbę.

**`plan_location` ma pewność i flagę weryfikacji.** Pozycje z OCR są niepewne
z definicji, ręcznie wskazane — pewne. Interfejs je rozróżnia, a OCR nigdy nie
nadpisuje wskazania człowieka.

---

## Struktura katalogów

```
app/
├── models/          ORM + słowniki typów
├── services/        logika bez Flaska
│   ├── pdf_profile_parser.py   odczyt profili po współrzędnych
│   ├── importer.py             PDF + osnowa → baza
│   ├── xlsx_importer.py        Excel → baza + walidacja krzyżowa
│   ├── plan_ocr.py             próba odczytu planów
│   ├── rury.py                 przelicznik 3 m / 6 m / mieszany
│   ├── materialy.py            wykaz materiałów odcinka
│   └── leveling.py             obliczenia niwelacyjne
├── blueprints/      main, api, szukaj, mapa, niwelator
├── templates/       Jinja2 (layouts / pages / partials)
└── static/vendor/   jQuery, Bootstrap, Tailwind — offline
docs/
├── project-docs/       ta dokumentacja
└── sonnet-think-output/ analizy źródeł danych
tests/                68 testów
```

---

## Komendy

```bash
flask db-wait                      # czekaj na Postgres
flask init-db                      # utwórz tabele
flask import-wszystko              # osnowa + profile + Excel
flask import-osnowa / import-profile / import-xlsx
flask ocr-plany [--zapisz]         # próba OCR planów
flask statystyki                   # co jest w bazie
flask pokaz-odcinek Wyl101 D155
```

---

## Uwagi eksploatacyjne

- **Zmiana kolumn w modelu wymaga migracji.** `db.create_all()` nie dodaje
  kolumn do istniejącej tabeli. Flask-Migrate jest podpięty; przy zmianach
  ad hoc trzeba usunąć i odtworzyć tabelę oraz powtórzyć import.
- **Cache map** leży w `data/exports/mapy/` — można go skasować w każdej chwili,
  odtworzy się przy pierwszym żądaniu.
- **Obraz z tesseractem waży ok. 1,2 GB.** Bez OCR (usunięcie `tesseract-ocr*`
  z `Dockerfile`) schodzi do ~330 MB.

---

## Doszło w etapie 4

| Narzędzie | Po co | Dlaczego akurat to |
|---|---|---|
| **Leaflet 1.9.4** | mapa z płynnym zoomem, warstwami i podziałką | standard w narzędziach tego typu; 160 kB, wgrany lokalnie jak reszta bibliotek — na budowie bywa bez zasięgu. Ładuje się **tylko na `/mapa`**, nie na każdej stronie |
| **`qrcode` 8.0** | kody QR na studnie | czysty Python, rysuje przez Pillow, które i tak było w projekcie |
| PyMuPDF `get_displaylist()` | kafelki mapy | 25 razy szybciej niż renderowanie strony od nowa przy każdym kafelku (5,18 s → 0,21 s na 12 kafelków) |
| PyMuPDF `show_pdf_page()` | wycinek profilu z oryginału | kopiuje **wektor**, nie obrazek — wycinek da się powiększać i drukować w jakości oryginału |
| Service Worker (bez biblioteki) | praca bez zasięgu | dwie strategie cache to ~100 linii; Workbox dokładałby narzędzia budowania, których projekt nie ma |

### Czego świadomie nie dodano

- **`ezdxf`** — DXF R12 to kilkadziesiąt linii własnego kodu, a czyta go każdy
  CAD. Zależność nie zarobiłaby na siebie.
- **`numpy`/`scipy`** — przekształcenie Helmerta ma cztery niewiadome i zamknięty
  wzór. Przy takiej skali przejrzystość jest cenniejsza niż ogólność.
- ~~**`pyproj`**~~ — **dodany w etapie 6.** Zapowiedź się spełniła: GPS
  z telefonu podaje WGS84, a plany są w PL-2000/5, więc transformacja między
  układami stała się konieczna. Odwzorowania Gaussa-Krügera nie pisze się
  ręcznie — błąd w szóstym miejscu po przecinku daje kilkanaście metrów
  w terenie i widać go dopiero przez porównanie z punktem kontrolnym.
