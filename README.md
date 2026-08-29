# Budowa All-in-One — narzędzie dla kierowników budów i brygadzistów (wod-kan)

Interaktywne narzędzie, które wyciąga dane wykonawcze z dokumentacji projektowej
(profile podłużne w PDF, zestawienia w Excelu, osnowa geodezyjna) do bazy
PostgreSQL i udostępnia je jako graf **obiektów** i **odcinków** — plus
kalkulator niwelacyjny.

Dane wzorcowe: obwodnica **Krosna Odrzańskiego, DK29** (GDDKiA / POLAQUA / Highway).

---

## Szybki start

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python -m flask import-wszystko
docker compose exec web python -m flask utworz-admina    # konto + hasło
```

Komenda `utworz-admina` zakłada konto **`budowa-adm`** z losowym hasłem, wypisuje
je raz na ekranie i dopisuje do `.env`. W bazie zostaje wyłącznie skrót.

| Usługa | Adres |
|---|---|
| Aplikacja | <http://localhost:8000> |
| Adminer (podgląd bazy) | <http://localhost:8080> — serwer `db`, user/hasło `budowa` |
| PostgreSQL | `localhost:5433` |

---

## Co narzędzie robi

**Czyta `docs/Profile Scalone.pdf`** — 13 arkuszy profili podłużnych — i rozbija
je na pojedyncze obiekty i odcinki:

```
13 arkuszy → 465 profili → 1059 obiektów → 649 odcinków → 7 439,5 m sieci
```

Dla każdego **obiektu** (`Wyl101`, `D155`, `Wp65`, `SEP3`, `O1a`, `Tr1`, `Ł2`, `KT15`)
zapisuje rzędną dna kanału, rzędną dna studni, rzędne terenu istniejącego
i projektowanego, zagłębienie, średnice i opis projektanta.

Dla każdego **odcinka** (`Wyl101–D155`) — długość, średnicę, spadek, rzędne
na obu końcach i kierunek rysunku.

**Kontroluje dane krzyżowo** z `Materiał.xlsx` i raportuje każdą rozbieżność
zamiast ją ukrywać.

**Liczy niwelację** — ile ma pokazać łata, żeby dno kanału wyszło na rzędnej
projektowej, z kontrolą wykonalności pomiaru z danego stanowiska.

**Przelicza rury** — wykonawca ma rury **3 m i 6 m**. Dla każdego odcinka podaje
zapotrzebowanie w trzech wariantach (same 3 m / same 6 m / mieszany) wraz
z długością docinki, odpadem i liczbą cięć.

**Wyszukuje** — wpisz `D155`, a dostaniesz wszystkie odcinki z jego udziałem:
rysunek profilu, tabelkę, wykaz materiałów, przelicznik rur i wycinek planu.

**Tyczy ciąg rur** — podaje, co ma zobaczyć osoba przy niwelatorze, gdy monter
postawi łatę na górnym karbie. Liczy rzeczywisty spadek po odjęciu średnic studni,
w dwóch trybach interpretacji rzędnych.

**Pilnuje dostępu i zadań** — całe narzędzie jest za logowaniem, ma panel kont
z rolami i listę zadań globalnych oraz przypisanych.

---

## Komendy

```bash
docker compose exec web python -m flask import-wszystko      # pełny import
docker compose exec web python -m flask import-osnowa        # same repery
docker compose exec web python -m flask import-profile       # sam PDF
docker compose exec web python -m flask import-xlsx          # sam Excel
docker compose exec web python -m flask statystyki           # co jest w bazie
docker compose exec web python -m flask pokaz-odcinek Wyl101 D155
docker compose exec web python -m pytest -q                  # testy
```

---

## API

```
GET  /szukaj?q=D155          # główny widok roboczy (HTML)
GET  /api/szukaj?q=D155
GET  /api/podpowiedzi?q=D15
GET  /api/odcinek/Wyl101/D155/rury
GET  /mapa                   # przeglądarka planów + wskazywanie pozycji
GET  /mapa/odcinek/<od>/<do>.png
GET  /api/statystyki
GET  /api/obiekty?szukaj=D15&typ=STUDNIA
GET  /api/obiekty/D155
GET  /api/odcinki?szukaj=Wyl101&dn=500
GET  /api/odcinki/Wyl101/D155
GET  /api/profile            GET /api/profile/<id>
GET  /api/osnowa             GET /api/materialy
GET  /api/importy            GET /api/importy/<id>/ostrzezenia
POST /niwelator/oblicz       POST /niwelator/rzedna-posrednia
POST /niwelator/ciag         GET  /niwelator/spadek
```

Przykład:
```bash
curl -X POST http://localhost:8000/niwelator/oblicz \
  -H "Content-Type: application/json" \
  -d '{"rzedna_repera":85.20,"odczyt_wstecz":1.432,"obiekt":"D155","cel":"dno_kanalu"}'
```

---

## Struktura

```
app/
├── models/          # ORM: sheet, profile, network_object, segment, connection…
├── services/
│   ├── pdf_profile_parser.py   # odczyt profili z PDF (PyMuPDF, po współrzędnych)
│   ├── importer.py             # PDF + osnowa → baza
│   ├── xlsx_importer.py        # Materiał.xlsx → baza + walidacja krzyżowa
│   ├── plan_ocr.py             # próba odczytu planów (patrz docs/project-docs/04)
│   ├── rury.py                 # przelicznik 3 m / 6 m / mieszany
│   ├── materialy.py            # wykaz materiałów odcinka
│   └── leveling.py             # obliczenia niwelacyjne
│   ├── spadek_ciagu.py         # tyczenie ciągu rur — odczyt na łacie
├── blueprints/      # main, api, szukaj, mapa, niwelator, auth, panel, zadania
├── templates/       # Jinja2 + Bootstrap 5
└── static/vendor/   # jQuery 3.7.1, Bootstrap 5.3.3, Tailwind 3.4 — lokalnie,
                     # bez CDN, bo na budowie bywa bez zasięgu
docs/
├── Profile Scalone.pdf, Materiał.xlsx, !!_DK29_osnowa_ok_v1.txt
├── project-docs/                      # dokumentacja techniczna i instrukcja
│   ├── 00-przeglad-projektu.md
│   ├── 01-instrukcja-obslugi.md
│   ├── 02-technologie.md
│   ├── 03-przelicznik-rur.md           # rury 3 m i 6 m, algorytm, przykłady
│   ├── 04-ocr-planow.md                # plany: co się udało, a co nie
│   └── 05-api.md
└── sonnet-think-output/                # analizy źródeł danych
    ├── 01-niwelacja-podstawy.md        # reper, rzędne, niwelator, wzory
    ├── 02-analiza-profile-scalone.md   # jak czytam rysunek
    └── 03-model-danych.md              # schemat bazy i mapowanie
```

---

## Stos

Flask 3 · SQLAlchemy 2 · PostgreSQL 16 · PyMuPDF · openpyxl · gunicorn ·
Bootstrap 5 + Tailwind + jQuery · Docker Compose

---

## Warto wiedzieć

- **`Rz.d.` w opisie obiektu ≠ rzędna dna kanału.** To dno studni
  (osadnika/piaskownika), zwykle 0,50 m niżej — i to do niego kopie się wykop.
- **Zagłębienie ujemne jest poprawne** — wylot wystaje ze skarpy ponad teren.
- **Profile rysowane są od wylotu w górę zlewni**, więc dno rośnie wzdłuż
  rysunku, mimo że woda płynie w drugą stronę.
- **Studnia ma tyle rzędnych dna, ile wchodzi do niej rur.** Jako kanoniczną
  przyjmujemy najniższą (odpływ); reszta jest w wystąpieniach i włączeniach.
- **Rozbieżności nie są ukrywane** — zakładka *Importy* pokazuje 67 ostrzeżeń
  z PDF i 41 rozbieżności PDF↔XLSX. To lista miejsc do sprawdzenia
  w dokumentacji, nie błędy programu.
- **Rury PRAGMA opisane są średnicą zewnętrzną**: profilowe Ø300 to katalogowe
  OD315, a Ø600 to OD630. Bez tego przeliczenia te odcinki nie znalazłyby
  żadnej pozycji materiałowej.
- **Tailwind musi mieć prefiks `tw-`.** Bez niego jego utility zderzają się
  z Bootstrapem — `.collapse { visibility: collapse }` czyniło nawigację
  i rozwijane sekcje niewidocznymi. Pilnuje tego `tests/test_ui_regresja.py`.
- **Etykiety na planach sytuacyjnych są zamienione na krzywe** — automat ich nie
  odczyta (sprawdzone czterema metodami, `docs/project-docs/04-ocr-planow.md`).
  Pozycję obiektu wskazuje się raz, klikając w mapę na `/mapa`; potem wycinek
  mapy i odległości liczą się same.
