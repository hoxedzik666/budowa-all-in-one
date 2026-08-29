# Technologie i uzasadnienie wyborów

---

## Stos

| Warstwa | Wybór | Wersja |
|---|---|---|
| Backend | Flask | 3.0.3 |
| ORM | SQLAlchemy (styl 2.0) + Flask-SQLAlchemy | 2.0.36 / 3.1.1 |
| Baza | PostgreSQL | 16-alpine |
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
