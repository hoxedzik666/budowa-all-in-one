# Struktura projektu — co robi każdy plik i katalog

> Mapa kodu. Dla każdego modułu: **co robi**, **skąd bierze dane** i **dlaczego
> istnieje**. Kolejność mniej więcej taka, w jakiej dane płyną przez system.

---

## Przepływ danych — od PDF do ekranu

```
docs/*.pdf, *.xlsx, *.txt        ← dokumentacja projektowa (wsad, tylko do odczytu)
        │
        │  flask import-wszystko
        ▼
app/services/  pdf_profile_parser.py ─┐
               xlsx_importer.py       ├─→ importer.py ─→ PostgreSQL
               (osnowa w importer.py) ─┘
        │
        │  zapytania
        ▼
app/models/    ORM: obiekty, odcinki, profile, konta, zadania
        │
        ├─→ app/services/  rury.py · materialy.py · leveling.py · spadek_ciagu.py
        │                  (obliczenia — nie znają Flaska)
        ▼
app/blueprints/  main · szukaj · niwelator · mapa · api · auth · panel · zadania
        │
        ▼
app/templates/ + app/static/     ← Jinja2 + Bootstrap/Tailwind/jQuery/Leaflet
```

Plany sytuacyjne idą **osobnym torem**, bo ich konwersja trwa ponad dwie minuty
i nie da się jej zrobić w trakcie żądania:

```
docs/Plany sytuacyjne Scalone.pdf
        │  flask konwertuj-plany
        ▼
app/services/plan_wektor.py   ← filtr po stylu kreski, sklejanie polilinii
        │
        ▼
data/exports/siec/strona-NN.json      ← wynik na dysku (120 kB)
        │
        ├─→ plan_eksport.py  → GeoJSON · DXF · CSV
        └─→ /mapa            → warstwa sieci + kilometraż

app/services/kafelki.py       ← obraz arkusza, renderowany na żądanie
app/services/georef.py        ← przeliczenie punkt rysunku ↔ PL-2000/5
```

Zasada, która trzyma to w kupie: **serwisy nie znają Flaska**. Dzięki temu
`rury.py`, `leveling.py` i `spadek_ciagu.py` da się testować bez aplikacji
i bez bazy — i te testy biegną w ułamku sekundy.

---

## `app/models/` — warstwa danych (ORM)

| Plik | Co definiuje |
|---|---|
| `enums.py` | słowniki: typ obiektu (WYLOT/STUDNIA/WPUST…), branża (KD/KT), typ odniesienia rzędnych, źródło danych, status wykonania. Tu leży też mapa prefiksu kodu na typ (`Wyl` → WYLOT) |
| `network.py` | **rdzeń**: `Sheet` (arkusz PDF), `Profile` (profil podłużny), `NetworkObject` (obiekt), `ObjectOccurrence` (wystąpienie obiektu na profilu), `Segment` (odcinek), `Connection` (włączenia i przyłącza) |
| `survey.py` | `SurveyPoint` — punkty osnowy geodezyjnej, czyli repery |
| `material.py` | `MaterialItem` — arkusz RURY; zawiera `rozbierz_opis()`, która wyciąga z nazwy pozycji średnicę, długość sztuki i klasę SN |
| `plan.py` | `PlanSheet`, `PlanLocation` — arkusze planów i pozycje obiektów; `PlanGeoref`, `PlanAnchor` — związanie arkusza z układem PL-2000/5; `punkty_na_metry()` przelicza odległość na rysunku na metry |
| `wykonanie.py` | `PomiarWykonawczy` — rzędne zmierzone w wykopie. **Osobno od projektu**: pomiar nigdy go nie nadpisuje |
| `postep.py` | `ZmianaStatusu`, `RaportDzienny` — postęp robót; tu też reguły ścieżki stanów i uprawnień do odbioru (`wolno_ustawic`) |
| `zdjecie.py` | `Zdjecie` — zdjęcia z wykopu; w bazie sama ścieżka, pliki na dysku |
| `audit.py` | `ImportRun` — historia importów wraz z pełną listą rozbieżności |
| `user.py` | `User`, `Rola` — konta i uprawnienia; hasła wyłącznie jako skrót |
| `task.py` | `Task`, `StatusZadania`, `Priorytet` — zadania globalne i przypisane |

### Dlaczego `ObjectOccurrence` jest osobną tabelą

Studnia ma tyle rzędnych dna, ile wchodzi do niej rur — a każdy profil pokazuje
„swoją”. Kanoniczna w `NetworkObject` jest **najniższa** (rzędna odpływu),
pozostałe zostają przy wystąpieniach. Nic nie ginie, a widok obiektu pokazuje
jednoznaczną liczbę.

---

## `app/services/` — logika, bez Flaska

### `pdf_profile_parser.py` — odczyt profili podłużnych
Czyta `Profile Scalone.pdf` **po współrzędnych** (PyMuPDF). Rozpoznaje pasma
tabeli po nagłówkach w lewej kolumnie, dzieli arkusz na bloki (jeden blok = jeden
profil) po napisie `n.p.m.`, a dane węzła od danych odcinka odróżnia po
**orientacji tekstu**: pionowo = węzeł, poziomo = odcinek.

Rozstrzyga też węzły z kilkoma wlotami — wybiera trójkę (teren, dno, zagłębienie)
spełniającą niezmiennik `zagłębienie = teren proj. − dno`.

### `opcjonalne.py` — biblioteki, których gdzieś nie ma
`LeniwyModul` udaje moduł: import odkłada do pierwszego użycia, a gdy biblioteki
brak — zgłasza `BrakModulu` z komunikatem po polsku, który Flask zamienia na
stronę z kodem 503. Dzięki temu `import fitz` w blueprintcie mapy nie przewraca
całej aplikacji na telefonie, gdzie PyMuPDF się nie instaluje.
Opis: [`16-termux.md`](16-termux.md).

### `baza.py` — pragmy SQLite
Ustawia przy każdym połączeniu `journal_mode=WAL`, `foreign_keys=ON`
i `busy_timeout`. Bez pierwszego zapis blokuje odczyty, bez drugiego telefon
przyjmowałby dane, które Postgres by odrzucił.

### `importer.py` — PDF i osnowa do bazy
`importuj_profile()` zapisuje wynik parsera, `importuj_osnowe()` wczytuje repery
z pliku `nazwa,X,Y,H`. Prowadzi `ImportRun` z listą ostrzeżeń.

### `xlsx_importer.py` — arkusz materiałowy
Wczytuje Studnie / Wpusty / Wyloty / RURY. **PDF jest źródłem geometrii** — gdy
Excel podaje inną wartość, nie nadpisuje, tylko zapisuje rozbieżność. Z arkusza
Wpusty bierze kolumnę `Odbiornik`, czyli jawny graf połączeń.

### `rury.py` — przelicznik rur
Wykonawca ma rury **3 m i 6 m**. Liczy trzy warianty (same 3 m, same 6 m,
mieszany) z docinkami i odpadem. Zawiera mapę `PROFIL_NA_OD` — rury PRAGMA
opisane są średnicą zewnętrzną, więc Ø300 → OD315, Ø600 → OD630.
Szczegóły: [`03-przelicznik-rur.md`](03-przelicznik-rur.md).

### `materialy.py` — wykaz materiałów odcinka
Arkusz RURY to magazyn całej budowy, nie przedmiar odcinkowy — wykaz trzeba
policzyć. Łączy odcinek z pozycjami katalogowymi po średnicy zewnętrznej
i klasie SN (czytanej z uwag obiektu).

### `leveling.py` — obliczenia niwelacyjne
`HI = rzędna repera + odczyt wstecz`, `odczyt zadany = HI − rzędna projektowa`,
kontrola ciągu niwelacyjnego, przykrycie. Sprawdza też **wykonalność**: odczyt
poniżej zera albo powyżej 4 m oznacza, że z tego stanowiska się nie da.

### `spadek_ciagu.py` — tyczenie ciągu rur
Odejmuje promienie studni od długości osiowej, liczy spadek w dwóch trybach
(rzędne przy ścianie studni albo w osi) i podaje **odczyt na łacie** w każdym
punkcie — z uwzględnieniem wysokości od cieku do górnego karba.

### `walidacja.py` — kontrola jakości danych
Sprawdza niezmiennik rzędnych, długości, spadki i rozjazd rysunek ↔ rzędne.
**Nie zgaduje poprawnych wartości** — oznacza odcinki flagą `podejrzany`
z podanym powodem. Uruchamia się po każdym imporcie i komendą `audyt-danych`.
Szczegóły: [`11-audyt-danych.md`](11-audyt-danych.md).

### `schemat.py` — dostosowanie istniejącej bazy
`db.create_all()` tworzy tylko brakujące tabele, nie dotyka istniejących.
Ten moduł dokłada brakujące kolumny i indeksy (`ADD COLUMN IF NOT EXISTS`),
żeby zmiana modelu nie wymagała kasowania bazy razem z ręcznie wskazanymi
pozycjami na planach.

### `plan_wektor.py` — wycięcie sieci z planów sytuacyjnych
Filtruje ścieżki wektorowe po **stylu kreski** odczytanym z legendy, skleja je
w polilinie i wyciąga żywe etykiety kilometrażu. Zastępuje OCR.
Szczegóły: [`09-konwerter-planow.md`](09-konwerter-planow.md).

### `plan_eksport.py` — GeoJSON, DXF, CSV
Zapis wyciętej sieci dla geodety i CAD. Każdy plik mówi w środku, w jakim jest
układzie. DXF piszemy sami w wersji R12 — czyta go każdy CAD, a to kilkadziesiąt
linii zamiast kolejnej zależności.

### `georef.py` — związanie arkusza z terenem
Przekształcenie Helmerta z dwóch (lub więcej) wskazanych punktów o znanych
współrzędnych. Podaje skalę, obrót i odchyłkę, żeby dało się ocenić, czy
dopasowanie ma sens. Szczegóły: [`10-georeferencja.md`](10-georeferencja.md).

### `kafelki.py` — serwer kafelków mapy
Renderuje fragmenty 256 × 256 px na żądanie. Sedno wydajności to **lista
wyświetlania** budowana raz na stronę — 25 razy szybciej niż renderowanie
strony od nowa przy każdym kafelku.

### `wycinek_pdf.py` — fragment oryginalnego rysunku profilu
Składa dwa pasy tej samej strony: kolumnę podpisów pasm i sam profil.
Kopiuje **wektor**, nie obrazek, więc wynik da się powiększać i drukować
w jakości oryginału. Uruchamia się wyłącznie na żądanie.

### `plan_ocr.py` — próba odczytu planów (droga historyczna)
Etykiety na planach są krzywymi; OCR dał zero trafień. Moduł zostaje wraz
z komendą `ocr-plany` jako zapis tego, czego próbowano.
Dlaczego nie wyszło: [`04-ocr-planow.md`](04-ocr-planow.md).

---

## `app/blueprints/` — warstwa HTTP

| Plik | Odpowiada za |
|---|---|
| `main.py` | pulpit i widoki tabelaryczne: odcinki, obiekty, profile, osnowa, materiały, importy |
| `szukaj.py` | **wyszukiwarka** — jedno pole daje obiekt, jego odcinki, materiały i rury; plus podpowiedzi |
| `niwelator.py` | kalkulator niwelacyjny i tyczenie ciągu rur |
| `mapa.py` | przeglądarka planów, wycinki map, ręczne wskazywanie pozycji obiektów |
| `api.py` | API JSON dla danych sieci |
| `auth.py` | logowanie i wylogowanie; lista endpointów jawnych |
| `wykonanie.py` | dziennik wykonawczy: pomiary, odchyłki, rzeczywisty spadek |
| `postep.py` | stan odcinków (`/postep`) i raporty dzienne (`/raporty`) |
| `zdjecia.py` | wysyłka i podawanie zdjęć z budowy |
| `pwa.py` | praca offline (service worker, `/offline`) i kody QR na studnie |
| `panel.py` | zarządzanie kontami (tylko rola ADMIN) |
| `zadania.py` | zadania globalne i przypisane, licznik do nawigacji |

---

## `app/templates/` — widoki Jinja2

```
layouts/base.html          szkielet: nawigacja, motywy, komunikaty, skrypty
partials/
  rysunek.html             makro rysujące profil podłużny w SVG
  karta_odcinka.html       pełna karta odcinka (profil + wycinek oryginału + tabelka
                           + materiały + rury + wykonanie + mapka)
  warianty_rur.html        tabela trzech wariantów pocięcia rur
  przelacznik_motywu.html  menu wyboru motywu
  przyciski_stanu.html     przyciski przesuwające odcinek po ścieżce robót
pages/
  pulpit.html              strona główna z podglądem planu
  szukaj.html              wyszukiwarka — główny widok roboczy
  obiekt.html / obiekty.html / odcinki.html / profil.html / profile.html
  niwelator.html           kalkulator pojedynczego punktu
  spadek_ciagu.html        tyczenie całego ciągu rur
  mapa.html                Leaflet: kafelki, warstwy, skala, kotwice georeferencji
  wykonanie.html           dziennik wykonawczy (as-built)
  postep.html              stan odcinków i pasek postępu całej sieci
  raporty.html             raporty dzienne brygady
  karta_druk.html          karta odcinka na jedną kartkę A4
  qr.html                  arkusz kodów QR do wydruku
  offline.html             ekran przy braku zasięgu
  osnowa.html / materialy.html / importy.html
  login.html               ekran logowania (własny szkielet, poza base.html)
  panel.html               konta użytkowników
  zadania.html             lista i dodawanie zadań
```

---

## `app/static/` — zasoby front-endu

| Ścieżka | Zawartość |
|---|---|
| `css/app.css` | style własne: kafelki, gęste tabele, rysunek SVG profilu |
| `css/motywy.css` | cztery motywy — patrz [`08-motywy.md`](08-motywy.md) |
| `service-worker.js` | praca bez zasięgu — patrz [`12`](12-praca-w-terenie.md) |
| `manifest.webmanifest`, `ikony/` | instalacja aplikacji na telefonie |
| `js/app.js` | formatowanie liczb po polsku, filtr tabel, kopiowanie do schowka, przełącznik motywu |
| `js/telefon.js` | GPS, aparat i skaner QR — **działa tylko wewnątrz APK** |
| `js/service-worker.js` | praca bez zasięgu: statyki z cache, dane najpierw z sieci |
| `manifest.webmanifest` · `ikony/` | instalacja na telefonie |
| `vendor/` | **jQuery 3.7.1, Bootstrap 5.3.3 + Icons, Tailwind 3.4, Leaflet 1.9.4 — lokalnie, bez CDN.** Na budowie bywa bez zasięgu |

⚠️ **Tailwind musi mieć prefiks `tw-`.** Bez niego jego utility zderzają się
z komponentami Bootstrapa — `.collapse { visibility: collapse }` czyniło
nawigację i rozwijane sekcje niewidocznymi. Pilnuje tego `tests/test_ui_regresja.py`.

---

## Pozostałe katalogi

| Katalog | Przeznaczenie |
|---|---|
| `docs/` | **dokumentacja projektowa — wsad, tylko do odczytu.** PDF-y, Excel, osnowa |
| `docs/project-docs/` | ta dokumentacja techniczna |
| `docs/sonnet-think-output/` | analizy źródeł danych: jak czytamy rysunek, model danych, podstawy niwelacji |
| `data/exports/mapy`, `kafelki`, `wycinki` | cache obrazów. Można kasować — odtworzy się |
| `data/exports/siec` | wynik konwertera planów. Kasowanie wymaga ponownego `flask konwertuj-plany` (~2 min) |
| `data/zdjecia/` | **zdjęcia z wykopu — nie kasować.** Nie odtworzą się; wykop zostanie zasypany |
| `.apk/` | projekt aplikacji na Androida wraz ze środowiskiem budowania w Dockerze |
| `termux/` | skrypty uruchomienia serwera na telefonie: `instaluj.sh`, `uruchom.sh`, `autostart.sh` |
| `scripts/` | pomocnicze skrypty jednorazowe, uruchamiane ręcznie w kontenerze |
| `tests/` | testy: 299 sztuk |
| `migrations/` | katalog Flask-Migrate (Alembic) |

---

## Pliki w katalogu głównym

| Plik | Rola |
|---|---|
| `wsgi.py` | punkt wejścia dla gunicorna |
| `app/__init__.py` | fabryka aplikacji: rejestracja rozszerzeń, blueprintów, filtrów, ochrony logowaniem |
| `app/config.py` | konfiguracja z zmiennych środowiskowych |
| `app/extensions.py` | `db`, `migrate`, `login_manager` — osobno, żeby uniknąć cyklicznych importów |
| `app/cli.py` | komendy `flask …`: import danych, zarządzanie kontami, statystyki |
| `Dockerfile` | obraz aplikacji (Python 3.12 + PyMuPDF + tesseract) |
| `docker-compose.yml` | trzy usługi: `web`, `db` (Postgres 16), `adminer` |
| `.env` | sekrety i konfiguracja lokalna — **w `.gitignore`** |

---

## Komendy

```bash
# baza i dane
flask db-wait                    # czekaj na Postgres
flask init-db                    # utwórz tabele
flask import-wszystko            # osnowa + profile + Excel
flask import-osnowa | import-profile | import-xlsx
flask konwertuj-plany            # wytnij sieć z planów (wektor, ~2 min)
flask konwertuj-plany --strony 5,9
flask audyt-danych               # kontrola jakości danych
flask ocr-plany [--zapisz]       # droga historyczna, patrz 04
flask statystyki                 # co jest w bazie
flask pokaz-odcinek Wyl101 D155

# konta
flask utworz-admina              # konto startowe + hasło do .env
flask zmien-haslo <login>
flask lista-kont
```

---

## Testy

```
tests/test_parser_profili.py   odczyt PDF, niezmienniki rzędnych
tests/test_rury.py             przelicznik 3 m / 6 m / mieszany
tests/test_niwelacja.py        HI, odczyt zadany, ciąg niwelacyjny
tests/test_spadek_ciagu.py     tyczenie ciągu, odejmowanie średnic studni, karb
tests/test_szukaj.py           wyszukiwarka i wykaz materiałów
tests/test_api.py              API i renderowanie stron
tests/test_auth.py             logowanie, konta, zadania
tests/test_ui_regresja.py      kolizja Tailwind/Bootstrap, motywy
tests/test_walidacja.py        jakość danych, odporność importu na powtórzenie
tests/test_wycinek_pdf.py      wycinek oryginału: legenda, przycięcie, cache
tests/test_plan_wektor.py      konwerter planów, eksporty, kafelki
tests/test_georef.py           przekształcenie Helmerta, kontrola dopasowania
tests/test_wykonanie.py        dziennik as-built, offline, kody QR
tests/test_postep.py           uprawnienia ról, ścieżka stanów, raporty dzienne
tests/test_gps.py              transformacja WGS84 → PL-2000/5 na osnowie
tests/test_zdjecia.py          zmniejszanie, EXIF, zapis na dysku
tests/test_apk.py              wpięcie funkcji telefonu, projekt Androida
tests/conftest.py              fixture — w tym pułapka z kontekstem aplikacji
```

`conftest.py` zawiera opis niuansu, który potrafi zjeść godzinę: Flask nie tworzy
nowego kontekstu aplikacji, gdy jakiś jest już aktywny, więc trzymanie jednego
kontekstu na całą sesję testową powoduje wyciekanie `g._login_user` między testami.
Dlatego **każdy** klient testowy czyści ten cache przed żądaniem — inaczej test
używający dwóch kont naraz (kierownik i monter) wykonałby oba żądania jako osobę,
która zalogowała się pierwsza, i cicho przepuścił błąd w uprawnieniach.
