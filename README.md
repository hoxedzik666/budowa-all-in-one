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
docker compose exec web python -m flask konwertuj-plany  # sieć z planów (~2 min)
docker compose exec web python -m flask utworz-admina    # konto + hasło
```

Komenda `utworz-admina` zakłada konto **`budowa-adm`** z losowym hasłem, wypisuje
je raz na ekranie i dopisuje do `.env`. W bazie zostaje wyłącznie skrót.

| Usługa | Adres |
|---|---|
| Aplikacja | <http://localhost:8000> |
| Adminer (podgląd bazy) | <http://localhost:8080> — serwer `db`, user/hasło `budowa` |
| PostgreSQL | `localhost:5433` |

### Na telefonie, bez komputera (Termux)

Całe narzędzie uruchamia się też **w kieszeni** — serwer, baza i wszystko inne
stoi na telefonie, a otwiera się to przeglądarką albo aplikacją z `.apk/`:

```bash
pkg install git                                   # w Termuxie
git clone <adres-repozytorium> ~/budowa-all-in-one
cd ~/budowa-all-in-one
./termux/instaluj.sh        # paczki, baza (SQLite), konto admina
./termux/uruchom.sh         # http://127.0.0.1:8000
```

Dane przenosi się z komputera jednym plikiem (`flask zrzut-sqlite` → podmiana
`data/budowa.sqlite3`), bo import z PDF wymaga PyMuPDF, którego na Androidzie
nie ma — mapa i wycinki oryginału zostają wtedy na komputerze, a reszta
narzędzia działa normalnie. Szczegóły:
[`docs/project-docs/16-termux.md`](docs/project-docs/16-termux.md).

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
z czterema rolami (admin, kierownik, brygadzista, **monter**) i listę zadań
globalnych oraz przypisanych.

**Śledzi postęp robót** — każdy odcinek idzie ścieżką
*wytyczony → w trakcie → wykonany → odebrany*, z historią zmian. Zgłosić
wykonanie może każdy, kto był w wykopie; **odebrać — tylko kierownik**.
Na mapie widać stan robót kolorem, a raport dzienny brygady zapisuje metry,
ludzi, sprzęt i przestoje.

**Wycina sieć z planów sytuacyjnych** — bez OCR-u. Rysunek jest czystym wektorem,
a kanalizacja deszczowa ma na nim własny styl kreski, odczytany z legendy.
Wynik: **8 952,9 m sieci w 704 poliliniach** plus 40 etykiet kilometrażu.
Eksport do GeoJSON, DXF i CSV.

**Wiąże arkusz z terenem** — wskazujesz dwa repery z osnowy, a program liczy
przekształcenie Helmerta. Od tego momentu kliknięcie w mapę podaje X, Y
w **PL-2000/5**, a repery same pojawiają się na planie.

**Pokazuje oryginał** — na żądanie wycina z PDF-a dokładnie ten fragment rysunku,
razem z kolumną podpisów pasm. Wektorowo, więc da się go powiększać i drukować.
Po to, żeby dało się sprawdzić, czy liczby w aplikacji zgadzają się z projektem.

**Prowadzi dziennik wykonawczy** — rzędne z wykopu, odchyłki od projektu
i rzeczywisty spadek. **Pomiar nigdy nie nadpisuje projektu.**

**Działa bez zasięgu** — instaluje się na telefonie i otwiera raz obejrzane
strony offline. Do tego kody QR na studnie i karta odcinka do druku na A4.

**Mieści się w telefonie** — cały serwer razem z bazą uruchamia się w Termuxie
i odpowiada pod `127.0.0.1:8000`, więc na budowie bez komputera i bez Wi-Fi
nadal widać rzędne, spadki i zapotrzebowanie na rury.

---

## Komendy

```bash
docker compose exec web python -m flask import-wszystko      # pełny import
docker compose exec web python -m flask import-osnowa        # same repery
docker compose exec web python -m flask import-profile       # sam PDF
docker compose exec web python -m flask import-xlsx          # sam Excel
docker compose exec web python -m flask konwertuj-plany      # sieć z planów (wektor)
docker compose exec web python -m flask audyt-danych         # kontrola jakości danych
docker compose exec web python -m flask statystyki           # co jest w bazie
docker compose exec web python -m flask zrzut-sqlite         # cała baza w jednym pliku (na telefon)
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
GET  /mapa                   # mapa: zoom, warstwy, skala, georeferencja
GET  /mapa/kafelek/<nr>/<z>/<x>/<y>.png
GET  /mapa/odcinek/<od>/<do>.png
GET  /mapa/eksport/<nr>.geojson|.dxf|.csv|.pgw
POST /api/mapa/kotwica       GET /api/mapa/repery/<nr>
GET  /profil/<id>/wycinek.pdf      # wektorowy wycinek oryginału
GET  /odcinek/<od>/<do>/karta      # karta do druku A4
GET  /api/wykonanie/odcinek/<od>/<do>
GET  /postep                 POST /postep/<id>/stan
GET  /api/postep/odcinek/<od>/<do>
GET  /api/mapa/postep/<nr>   # warstwa postępu na arkuszu
GET  /raporty                POST /raporty/dodaj
GET  /qr  ·  /qr/<kod>.png
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
│   ├── walidacja.py            # kontrola jakości danych, flaga „podejrzany”
│   ├── schemat.py              # dokładanie kolumn do istniejącej bazy
│   ├── plan_wektor.py          # wycięcie sieci z planów po stylu kreski
│   ├── plan_eksport.py         # GeoJSON / DXF / CSV
│   ├── georef.py               # związanie arkusza z PL-2000/5 (Helmert)
│   ├── kafelki.py              # serwer kafelków mapy
│   ├── wycinek_pdf.py          # fragment oryginalnego rysunku profilu
│   ├── powiazania.py           # „D155" / „Wyl101-D155" → obiekt lub odcinek
│   ├── plan_ocr.py             # droga historyczna (patrz project-docs/04)
│   ├── rury.py                 # przelicznik 3 m / 6 m / mieszany
│   ├── materialy.py            # wykaz materiałów odcinka
│   ├── leveling.py             # obliczenia niwelacyjne
│   ├── spadek_ciagu.py         # tyczenie ciągu rur — odczyt na łacie
│   ├── opcjonalne.py           # biblioteki, których na telefonie nie ma
│   └── baza.py                 # pragmy SQLite (WAL, klucze obce, oczekiwanie)
├── blueprints/      # main, api, szukaj, mapa, niwelator, auth, panel,
│                    # zadania, wykonanie, postep, pwa
├── templates/       # Jinja2 + Bootstrap 5
└── static/vendor/   # jQuery 3.7.1, Bootstrap 5.3.3, Tailwind 3.4, Leaflet 1.9.4
                     # — lokalnie, bez CDN, bo na budowie bywa bez zasięgu
termux/              # uruchomienie serwera na telefonie (instaluj / uruchom / autostart)
.apk/                # powłoka Capacitora: GPS, aparat, skaner QR
docs/
├── Profile Scalone.pdf, Materiał.xlsx, !!_DK29_osnowa_ok_v1.txt
├── project-docs/                      # dokumentacja techniczna i instrukcja
│   ├── 00-przeglad-projektu.md
│   ├── 01-instrukcja-obslugi.md
│   ├── 02-technologie.md
│   ├── 03-przelicznik-rur.md           # rury 3 m i 6 m, algorytm, przykłady
│   ├── 04-ocr-planow.md                # plany OCR-em: droga historyczna
│   ├── 05-api.md
│   ├── 06-struktura-projektu.md        # co robi każdy plik
│   ├── 07-uwierzytelnianie-i-uzytkownicy.md
│   ├── 08-motywy.md
│   ├── 09-konwerter-planow.md          # sieć z rysunku po stylu kreski
│   ├── 10-georeferencja.md             # związanie arkusza z terenem
│   ├── 11-audyt-danych.md              # co było zepsute i jak naprawione
│   ├── 12-praca-w-terenie.md           # dziennik, offline, kody QR
│   ├── 13-android-apk.md               # przeniesienie na Androida: analiza
│   ├── 14-postep-robot.md              # stan odcinków, raporty, rola montera
│   ├── 15-aplikacja-android.md         # powłoka Capacitora: GPS, aparat, QR
│   └── 16-termux.md                    # cały serwer na telefonie (SQLite)
└── sonnet-think-output/                # analizy źródeł danych
    ├── 01-niwelacja-podstawy.md        # reper, rzędne, niwelator, wzory
    ├── 02-analiza-profile-scalone.md   # jak czytam rysunek
    └── 03-model-danych.md              # schemat bazy i mapowanie
```

---

## Stos

Flask 3 · SQLAlchemy 2 · PostgreSQL 16 (na telefonie: SQLite) · PyMuPDF ·
openpyxl · qrcode · gunicorn · Bootstrap 5 + Tailwind + jQuery + Leaflet ·
Service Worker · Docker Compose · Capacitor 7 (APK) · Termux

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
  z PDF i 41 rozbieżności PDF↔XLSX, plus **5 odcinków oznaczonych jako
  podejrzane** (długość 0,00 m, spadek 31%). To lista miejsc do sprawdzenia
  w dokumentacji, nie błędy programu — poprawnych wartości nie zgadujemy.
- **Rury PRAGMA opisane są średnicą zewnętrzną**: profilowe Ø300 to katalogowe
  OD315, a Ø600 to OD630. Bez tego przeliczenia te odcinki nie znalazłyby
  żadnej pozycji materiałowej.
- **Tailwind musi mieć prefiks `tw-`.** Bez niego jego utility zderzają się
  z Bootstrapem — `.collapse { visibility: collapse }` czyniło nawigację
  i rozwijane sekcje niewidocznymi. Pilnuje tego `tests/test_ui_regresja.py`.
- **Etykiety na planach są krzywymi, ale rysunek nie jest ślepym zaułkiem.**
  OCR faktycznie nie odczyta ani jednego kodu — za to sieć da się wyciąć po
  **stylu kreski** odczytanym z legendy (`09-konwerter-planow.md`). Kodów
  obiektów to nie odzyska, bo ich w pliku po prostu nie ma; te wskazuje się raz,
  klikając w mapę.
- **Dwie kotwice georeferencji zawsze pasują idealnie** — cztery równania,
  cztery niewiadome. Odchyłka nic wtedy nie mówi; sprawdzianem jest dopiero
  trzecia kotwica, a przy dwóch — zgodność skali z 1:1000.
- **Odległość na odcinku liczy się od pierwszego obiektu w nazwie.** Na
  `Wyl101-D155` metr zerowy jest przy `Wyl101` — mimo że profil rysowany jest
  od wylotu w górę, więc `od` bywa niższym końcem.
- **Import był podatny na powtórzenie** — dwukrotne uruchomienie dublowało
  połączenia (2442 wiersze zamiast 880), a rzędne z rysunku nigdy się nie
  odświeżały. Oba błędy naprawione i pilnowane testami (`11-audyt-danych.md`).
- **Zgłoszenie wykonania to nie odbiór.** Dwa osobne stany, bo na budowie robi
  je kto inny: brygada zgłasza, kierownik odbiera. Reguła jest sprawdzana po
  stronie serwera, nie tylko przez ukrycie przycisku.
- **Pole `status` istniało od etapu 1 i nigdy nie było ustawiane** — etap 5 je
  ożywił, zamiast dokładać nowe.
- **Nowa rola nie pojawi się w bazie sama.** `create_all()` tworzy typ enum raz
  i nigdy go nie rusza; wartości dokłada `app/services/schemat.py`. Operacja jest
  nieodwracalna — Postgres nie ma `DROP VALUE`.
- **Brak biblioteki to nie awaria.** PyMuPDF nie zainstaluje się na Androidzie,
  więc na telefonie nie ma mapy ani wycinków PDF. Zamiast błędu 500 wychodzi
  strona z kodem 503, która mówi, czego brakuje i gdzie tę rzecz zrobić.
  Pilnuje tego `app/services/opcjonalne.py`: `import fitz` jest leniwy, bo jeden
  import na poziomie modułu przewracał **całą** aplikację — łącznie z niwelatorem,
  który z PDF-em nie ma nic wspólnego.
- **Ten sam model opisuje dwie bazy.** `JSONB` istnieje tylko w Postgresie,
  więc kolumny JSON są zadeklarowane z wariantem (`app/models/typy.py`) —
  DDL Postgresa zostaje bez zmian, a SQLite dostaje zwykły `JSON`.
  Na telefonie **`PRAGMA journal_mode=WAL` nie jest ozdobą**: bez niej zapis
  pomiaru blokuje odczyty i przeglądanie odcinków kończy się „database is locked".
- **Kafelki mapy renderują się z listy wyświetlania PyMuPDF** — 25 razy szybciej
  niż przetwarzanie strony od nowa przy każdym kafelku. Bez tego zoom by się
  zacinał.
