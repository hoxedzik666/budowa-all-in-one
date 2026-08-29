# Przegląd projektu

> Dokumentacja techniczna narzędzia **Budowa All-in-One** — stan na etap 4.

---

## Po co to jest

Dane wykonawcze sieci kanalizacyjnej żyją w dwóch miejscach, z których żadne nie
nadaje się do użycia na budowie:

- **PDF-y profili podłużnych** — rysunki na arkuszach szerokości dwóch metrów,
  gdzie jedna studnia to pionowa kolumna czterech liczb,
- **arkusz Excela** — zestawienia zbiorcze na kilkaset wierszy.

Brygadzista przy wykopie potrzebuje odpowiedzi w piętnaście sekund: *jaka rzędna
dna na D155, ile metrów do następnej studni, jaki spadek, ile rur zabrać.*
Kierownik potrzebuje wiedzieć, czego brakuje i gdzie dokumentacja sama sobie
przeczy.

To narzędzie wyciąga te dane do bazy i podaje w formie, z której da się korzystać
w terenie.

---

## Dane źródłowe

Zadanie: **budowa obwodnicy miejscowości Krosno Odrzańskie w ciągu DK29**
(Inwestor: GDDKiA O/Zielona Góra, Wykonawca: POLAQUA, Projektant: Highway Sp. z o.o.).

| Plik | Co zawiera | Rola |
|---|---|---|
| `Profile Scalone.pdf` | 13 arkuszy profili podłużnych | **źródło geometrii** |
| `Materiał.xlsx` | Studnie / Wpusty / Wyloty / RURY | uzupełnienie + walidator |
| `!!_DK29_osnowa_ok_v1.txt` | 151 punktów osnowy `nazwa,X,Y,H` | repery do niwelacji |
| `Plany sytuacyjne Scalone.pdf` | 18 arkuszy planów 1:1000 | mapa, sieć wektorowa, kilometraż — patrz `09` |

---

## Co jest w bazie

```
13 arkuszy → 465 profili → 1059 obiektów → 649 odcinków → 7 439,5 m sieci
1114 wystąpień obiektów na profilach
 880 połączeń (100 z rysunku + 780 z arkusza)
 151 punktów osnowy
  32 pozycje materiałowe, w tym 19 pozycji rurowych w 7 średnicach
   5 odcinków oznaczonych jako podejrzane (patrz `11`)
```

Z planów sytuacyjnych, osobnym torem (`flask konwertuj-plany`):

```
18 arkuszy → 704 polilinie → 8 952,9 m sieci → 40 etykiet kilometrażu
```

Obiekty według typu:

| Typ | Ile |
|---|---|
| WPUST | 440 |
| WYLOT | 420 |
| STUDNIA | 158 |
| WEZEL_KT (kanał tłoczny) | 15 |
| OSADNIK | 13 |
| SEPARATOR | 9 |
| LUK | 3 |
| TROJNIK | 1 |

---

## Architektura

```
docs/*.pdf, *.xlsx, *.txt
        │
        ▼
  ┌──────────────────────────────────────────┐
  │ app/services/                            │
  │   pdf_profile_parser.py  ← profile       │
  │   xlsx_importer.py       ← Excel         │
  │   importer.py            ← osnowa + zapis│
  │   walidacja.py           ← kontrola      │
  │   plan_wektor.py         ← plany (wektor)│
  └──────────────┬───────────────────────────┘
                 ▼
          PostgreSQL 16
          (sheet, profile, network_object,
           object_occurrence, segment,
           connection, survey_point,
           material_item, plan_sheet,
           plan_location, plan_georef, plan_anchor,
           pomiar_wykonawczy, import_run)
                 │
     ┌───────────┴────────────┐
     ▼                        ▼
 app/services/           app/blueprints/
   rury.py                 szukaj.py   ← wyszukiwarka
   materialy.py            main.py     ← widoki tabelaryczne
   leveling.py             niwelator.py
   spadek_ciagu.py         mapa.py     ← Leaflet + kafelki
   georef.py               wykonanie.py ← dziennik as-built
   kafelki.py              pwa.py      ← offline + kody QR
   wycinek_pdf.py          api.py
                 │
                 ▼
        Jinja2 + Bootstrap 5 + Tailwind + jQuery
```

Warstwy są rozdzielone celowo: **serwisy nie znają Flaska**, więc dają się
testować bez aplikacji i bez bazy (patrz `tests/test_rury.py`,
`tests/test_niwelacja.py`).

---

## Co narzędzie potrafi

| Funkcja | Gdzie | Stan |
|---|---|---|
| Wyszukiwarka obiekt → odcinki | `/szukaj` | działa |
| Rysunek profilu (SVG) | karta odcinka, `/profil/<id>` | działa |
| Tabelka odcinka | karta odcinka | działa |
| Wykaz materiałów odcinka | karta odcinka | działa |
| Przelicznik rur 3 m / 6 m / mieszany | karta odcinka, `/api/odcinek/…/rury` | działa |
| Kalkulator niwelacyjny | `/niwelator` | działa |
| Kontrola krzyżowa PDF ↔ XLSX | `/importy` | działa |
| Przeglądarka planów | `/mapa` | działa |
| Automatyczne umiejscowienie obiektu na planie | OCR | **nie działa** — patrz `04` |
| Kilometraż z planów | `/mapa`, eksport | działa — żywy tekst, patrz `09` |
| Wycięcie sieci z planu (wektor) | `flask konwertuj-plany` | działa — 8,95 km, patrz `09` |
| Georeferencja arkusza (PL-2000/5) | `/mapa`, tryb Kotwica | działa — patrz `10` |
| Mapa z płynnym zoomem i skalą | `/mapa` | działa |
| Wycinek oryginału z PDF na żądanie | `/profil/<id>`, karta odcinka | działa |
| Eksport GeoJSON / DXF / CSV / .pgw | `/mapa/eksport/…` | działa |
| Dziennik wykonawczy (as-built) | `/wykonanie` | działa — patrz `12` |
| Praca offline (PWA) | cała aplikacja | działa — patrz `12` |
| Kody QR na studnie | `/qr` | działa |
| Karta odcinka do druku A4 | `/odcinek/<od>/<do>/karta` | działa |
| Audyt jakości danych | `flask audyt-danych`, `/importy` | działa — patrz `11` |
| Tyczenie ciągu rur (odczyt na łacie) | `/niwelator/ciag-rur` | działa |
| Podgląd planu na pulpicie | `/` | działa |
| Motywy graficzne | przełącznik w nawigacji | działa |
| Logowanie | `/login` | działa |
| Konta użytkowników | `/panel/uzytkownicy` | działa |
| Zadania globalne i przypisane | `/zadania` | działa |

---

## Uruchomienie

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python -m flask import-wszystko
docker compose exec web python -m flask konwertuj-plany   # sieć z planów (~2 min)
docker compose exec web python -m flask utworz-admina     # konto + hasło
docker compose exec web python -m flask audyt-danych      # kontrola jakości
docker compose exec web python -m pytest -q               # 213 testów
```

| Usługa | Adres |
|---|---|
| Aplikacja | <http://localhost:8000> |
| Adminer | <http://localhost:8080> (serwer `db`, user/hasło `budowa`) |
| PostgreSQL | `localhost:5433` |

---

## Pozostałe dokumenty

- [`01-instrukcja-obslugi.md`](01-instrukcja-obslugi.md) — jak używać, krok po kroku
- [`02-technologie.md`](02-technologie.md) — stos i uzasadnienie wyborów
- [`03-przelicznik-rur.md`](03-przelicznik-rur.md) — **rury 3 m i 6 m**, algorytm, przykłady
- [`04-ocr-planow.md`](04-ocr-planow.md) — plany sytuacyjne: co się udało, a co nie
- [`05-api.md`](05-api.md) — endpointy
- [`06-struktura-projektu.md`](06-struktura-projektu.md) — **co robi każdy plik i katalog**
- [`07-uwierzytelnianie-i-uzytkownicy.md`](07-uwierzytelnianie-i-uzytkownicy.md) — role, konta, zadania
- [`08-motywy.md`](08-motywy.md) — motywy graficzne i pułapka Tailwind/Bootstrap
- [`09-konwerter-planow.md`](09-konwerter-planow.md) — **jak z rysunku bez etykiet zrobić dane**
- [`10-georeferencja.md`](10-georeferencja.md) — związanie arkusza z układem PL-2000/5
- [`11-audyt-danych.md`](11-audyt-danych.md) — **co było zepsute w konwersji do bazy**
- [`12-praca-w-terenie.md`](12-praca-w-terenie.md) — dziennik wykonawczy, offline, kody QR

Analizy źródeł danych są w [`docs/sonnet-think-output/`](../sonnet-think-output/).
