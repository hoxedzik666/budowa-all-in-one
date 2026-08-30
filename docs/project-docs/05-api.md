# API

Wszystkie odpowiedzi to JSON w UTF-8, bez escapowania polskich znaków.
Liczby są zwracane jako `number`, nie jako tekst.

Baza: `http://localhost:8000`

---

## Wyszukiwarka

### `GET /api/szukaj?q=D155`

Komplet informacji o obiekcie: rzędne, wszystkie odcinki z jego udziałem wraz
z wykazem materiałów, połączenia i repery.

```json
{
  "obiekt": {
    "kod": "D155", "typ": "STUDNIA",
    "rzedna_dna_kanalu": 82.76, "rzedna_dna_studni": 82.26,
    "rzedna_terenu_proj": 83.81, "zaglebienie": 1.05,
    "glebokosc_wykopu": 1.55, "srednica_studni_mm": 1500
  },
  "odcinki": [{ "nazwa": "Wyl101-D155", "dlugosc_m": 20.5, "dn_mm": 500,
                "spadek_promile": 3.0, "wykaz_materialow": { … } }],
  "polaczenia": [ … ],
  "lokalizacja_na_planie": null,
  "repery_wysokosciowo": [ … ],
  "repery_najblizsze": { "dostepne": false, "repery": [], "powod": "…" }
}
```

`404`, gdy nie ma obiektu pasującego do frazy.

### `GET /api/podpowiedzi?q=D15`

Lista kodów do podpowiedzi w polu wyszukiwania (maks. 12).

```json
[{"kod": "D15", "typ": "STUDNIA"}, {"kod": "D150", "typ": "STUDNIA"}]
```

---

## Rury i materiały

### `GET /api/odcinek/<od>/<do>/rury`

Wykaz materiałów i przelicznik rur dla jednego odcinka.

```bash
curl http://localhost:8000/api/odcinek/Wyl101/D155/rury
```

```json
{
  "odcinek": "Wyl101-D155",
  "dlugosc_m": 20.5,
  "dn_profilowe": 500,
  "dn_katalogowe": 500,
  "klasa_sn": "SN8",
  "rury": {
    "dlugosci_handlowe": [3.0, 6.0],
    "zalecany": "mieszany",
    "warianty": [
      {"nazwa": "same_3m",  "opis_sztuk": "7 × 3 m",
       "sztuk_razem": 7, "material_m": 21.0,
       "docinka_m": 2.5, "odpad_m": 0.5, "liczba_ciec": 1},
      {"nazwa": "same_6m",  "opis_sztuk": "4 × 6 m",
       "sztuk_razem": 4, "material_m": 24.0,
       "docinka_m": 2.5, "odpad_m": 3.5, "liczba_ciec": 1},
      {"nazwa": "mieszany", "opis_sztuk": "3 × 6 m + 1 × 3 m",
       "sztuk_razem": 4, "material_m": 21.0,
       "docinka_m": 2.5, "odpad_m": 0.5, "liczba_ciec": 1}
    ]
  },
  "katalog": [ … pozycje z arkusza RURY … ],
  "obiekty": [ … obiekty na końcach … ],
  "braki": []
}
```

**Znaczenie pól:** `docinka_m` — kawałek, który idzie do wykopu;
`odpad_m` — co z tej rury zostaje; `material_m` — ile metrów wziąć z magazynu.
Zawsze `docinka + odpad = długość rury, z której cięto`.
Szczegóły: [`03-przelicznik-rur.md`](03-przelicznik-rur.md).

---

## Sieć

| Endpoint | Zwraca |
|---|---|
| `GET /api/statystyki` | liczby zbiorcze i podział na typy |
| `GET /api/obiekty?szukaj=D15&typ=STUDNIA&limit=200` | lista obiektów |
| `GET /api/obiekty/<kod>` | obiekt + wystąpienia + odcinki + połączenia |
| `GET /api/odcinki?szukaj=Wyl101&dn=500&limit=300` | lista odcinków |
| `GET /api/odcinki/<od>/<do>` | jeden odcinek z obiektami i profilem |
| `GET /api/profile?szukaj=D155` | lista profili |
| `GET /api/profile/<id>` | profil z węzłami i odcinkami |
| `GET /api/osnowa?szukaj=o10` | punkty osnowy |
| `GET /api/materialy` | arkusz RURY |
| `GET /api/importy` | historia importów |
| `GET /api/importy/<id>/ostrzezenia` | pełna lista rozbieżności, w tym wynik walidatora |
| `GET /api/zdrowie` | `{"status": "ok"}` |

---

## Niwelator

### `POST /niwelator/oblicz`

```bash
curl -X POST http://localhost:8000/niwelator/oblicz \
  -H "Content-Type: application/json" \
  -d '{"rzedna_repera":85.20,"odczyt_wstecz":1.432,
       "obiekt":"D155","cel":"dno_kanalu","odczyt_zmierzony":3.880}'
```

Zamiast `rzedna_repera` można podać `reper` (nazwę z osnowy), a zamiast
`obiekt` — `rzedna_projektowa`. `cel` to `dno_kanalu` albo `dno_studni`.

```json
{
  "hi": 86.632,
  "rzedna_projektowa": 82.76,
  "odczyt_zadany": 3.872,
  "odczyt_zmierzony": 3.88,
  "roznica": -0.008,
  "ocena": "OK",
  "wykonalne": true,
  "uwaga": null,
  "glebokosc_wykopu": 1.55,
  "przykrycie": 0.55
}
```

`wykonalne: false` + `uwaga`, gdy celowa biegnie poniżej punktu albo odczyt
wychodzi poza 4-metrową łatę.

### Pozostałe

| Endpoint | Do czego |
|---|---|
| `POST /niwelator/rzedna-posrednia` | rzędna dna w dowolnym punkcie odcinka |
| `POST /niwelator/ciag` | kontrola ciągu niwelacyjnego i odchyłki |
| `GET /niwelator/spadek?rzedna_od=&rzedna_do=&dlugosc_m=` | spadek z rzędnych |

---

## Plany sytuacyjne

| Endpoint | Zwraca |
|---|---|
| `GET /mapa/strona/<nr>.png?dpi=90` | cały arkusz |
| `GET /mapa/kafelek/<nr>/<z>/<x>/<y>.png` | **kafelek 256 × 256 px** — podstawa mapy z zoomem |
| `GET /api/mapa/strona/<nr>` | wymiary, skala, georeferencja, kotwice, wskazane pozycje |
| `GET /mapa/obiekt/<kod>.png` | wycinek wokół obiektu z zaznaczeniem |
| `GET /mapa/odcinek/<od>/<do>.png` | wycinek obejmujący oba końce |
| `POST /api/mapa/pozycja` | zapis ręcznie wskazanej pozycji |
| `DELETE /api/mapa/pozycja/<kod>` | usunięcie wskazania |

### Sieć wycięta z rysunku

| Endpoint | Zwraca |
|---|---|
| `GET /api/mapa/siec/<nr>` | polilinie i etykiety kilometrażu wycięte z arkusza |
| `GET /mapa/eksport/<nr>.geojson` | GeoJSON (QGIS) |
| `GET /mapa/eksport/<nr>.dxf` | DXF R12 (CAD) |
| `GET /mapa/eksport/<nr>.csv` | węzły do tyczenia |
| `GET /mapa/eksport/<nr>.pgw` | plik świata — **tylko po georeferencji** |

Wynik pochodzi z `flask konwertuj-plany`; bez tej komendy `api/mapa/siec`
zwraca `{"dostepne": false}` z powodem. Szczegóły:
[`09-konwerter-planow.md`](09-konwerter-planow.md).

### Georeferencja

| Endpoint | Do czego |
|---|---|
| `POST /api/mapa/kotwica` | wskaż punkt o znanych współrzędnych |
| `DELETE /api/mapa/kotwica/<id>` | usuń kotwicę i przelicz |
| `GET /api/mapa/wspolrzedne/<nr>?x_pt=&y_pt=` | punkt rysunku → X, Y w PL-2000/5 |
| `GET /api/mapa/repery/<nr>` | repery z osnowy naniesione na arkusz |

```bash
curl -X POST http://localhost:8000/api/mapa/kotwica   -H "Content-Type: application/json"   -d '{"strona_id":5,"x_pt":842.0,"y_pt":511.0,"reper":"o41"}'
```

```json
{"zapisano": true,
 "georef": {"skala_rysunku": 1000, "obrot_stopnie": 4.0,
            "rmse_m": 0.0, "liczba_kotwic": 2, "wiarygodne": true,
            "uklad": "PL-2000/5"}}
```

Poniżej dwóch kotwic `georef` jest `null` — nie zgadujemy.
Szczegóły: [`10-georeferencja.md`](10-georeferencja.md).

---

## Wycinek oryginalnego rysunku

| Endpoint | Zwraca |
|---|---|
| `GET /profil/<id>/wycinek.png?dpi=150&legenda=1` | fragment arkusza jako obraz |
| `GET /profil/<id>/wycinek.pdf?pobierz=1` | ten sam fragment **jako wektor** |
| `GET /odcinek/<od>/<do>/wycinek.png` | fragment obejmujący jeden odcinek |
| `GET /odcinek/<od>/<do>/wycinek.pdf` | jw., wektorowo |

Konwersja rusza **wyłącznie na żądanie**; wynik trafia do cache.
`legenda=0` pomija kolumnę podpisów pasm.

---

## Dziennik wykonawczy

| Endpoint | Do czego |
|---|---|
| `GET /wykonanie?zakres=` | lista pomiarów: `wszystkie`, `moje`, `poza-tolerancja` |
| `POST /wykonanie/dodaj` | nowy pomiar |
| `POST /wykonanie/<id>/usun` | usunięcie (autor albo admin) |
| `GET /api/wykonanie/odcinek/<od>/<do>` | pomiary, odchyłki i rzeczywisty spadek |

```json
{"odcinek": "Wyl101-D155", "pomiarow": 2, "poza_tolerancja": 0,
 "najwieksza_odchylka_m": 0.02,
 "spadek": {"dlugosc_m": 20.5, "spadek_promile": 3.9,
            "poprawny_kierunek": true, "roznica_do_projektu_promile": 0.9},
 "spadek_projektowy_promile": 3.0,
 "pomiary": [{"odleglosc_m": 0.0, "rzedna_projektowa": 82.7,
              "rzedna_zmierzona": 82.7, "odchylka_m": 0.0,
              "tolerancja_m": 0.02, "w_tolerancji": true}]}
```

**Pomiar nigdy nie nadpisuje projektu.** Odchyłka liczy się w locie.

---

## Postęp robót i raporty dzienne

| Endpoint | Do czego |
|---|---|
| `GET /postep?stan=&szukaj=` | przegląd stanów odcinków |
| `POST /postep/<id>/stan` | zmiana stanu (`stan=WYTYCZONY` … `ODEBRANY`) |
| `GET /api/postep/odcinek/<od>/<do>` | stan, następny krok, historia, ostrzeżenia |
| `GET /api/mapa/postep/<nr>?wszystkie=1` | warstwa postępu na arkuszu |
| `GET /raporty?dzien=&szukaj=` | raporty dzienne |
| `POST /raporty/dodaj` · `POST /raporty/<id>/usun` | operacje na raportach |
| `GET /api/raporty` | raporty widoczne dla zalogowanego + podsumowanie tygodnia |

```json
{"odcinek": "Wyl101-D155", "stan": "WYKONANY", "etykieta": "wykonany",
 "nastepny": {"stan": "ODEBRANY", "etykieta": "odebrany", "wolno": false,
              "powod": "Odbiór odcinka należy do kierownika budowy…"},
 "ostrzezenia": ["2 z 3 pomiarów jest poza tolerancją, największa odchyłka 0.045 m."],
 "historia": [{"poprzedni": "W_TRAKCIE", "nowy": "WYKONANY", "autor": "monter1"}]}
```

Pole `wolno` mówi wprost, czy zalogowana osoba może wykonać dany krok —
interfejs nie musi powielać reguł uprawnień. **Reguła i tak jest sprawdzana
po stronie serwera.**

Warstwa postępu zwraca `odcinki` (do narysowania), `polowiczne` (jeden koniec
wskazany) oraz `nie_do_narysowania` — bo pokazanie części odcinków bez powiedzenia
o reszcie wprowadzałoby w błąd.

---

## Praca offline i kody QR

| Endpoint | Do czego |
|---|---|
| `GET /service-worker.js` | skrypt offline (nagłówek `Service-Worker-Allowed: /`) |
| `GET /offline` | ekran przy braku zasięgu — **działa bez sesji** |
| `GET /qr` | arkusz kodów do wydruku |
| `GET /qr/<kod>.png?px=8` | pojedynczy kod QR |
| `GET /odcinek/<od>/<do>/karta` | karta odcinka na kartkę A4 |

Wycinki zwracają **`404` z komunikatem**, gdy obiekt nie ma jeszcze wskazanej
pozycji — nigdy pustego obrazu.

```bash
curl -X POST http://localhost:8000/api/mapa/pozycja \
  -H "Content-Type: application/json" \
  -d '{"kod":"D155","strona_id":9,"x_pt":1284.0,"y_pt":592.0}'
```

---

## Tyczenie ciągu rur

### `POST /niwelator/ciag-rur/oblicz`

Podaje, **co ma zobaczyć osoba przy niwelatorze**, gdy monter postawi łatę
na górnym karbie rury.

```bash
curl -X POST http://localhost:8000/niwelator/ciag-rur/oblicz \
  -H "Content-Type: application/json" \
  -d '{"od":"D114","do":"D115","rzedna_repera":45.350,"odczyt_wstecz":1.432,
       "h_karb":0.5,"tryb":"SCIANA","krok":"6"}'
```

| Pole | Znaczenie |
|---|---|
| `od`, `do` | początek i koniec ciągu (`do` opcjonalne — inaczej do końca ciągu) |
| `reper` / `rzedna_repera` + `odczyt_wstecz`, albo `hi` | stanowisko niwelatora |
| `rzedna_dna_start` | **zmierzona** rzędna dna; puste = wartość projektowa |
| `h_karb` | wysokość od cieku do górnego karba; puste = średnica zewnętrzna rury |
| `tryb` | `SCIANA` (spadek stromszy) albo `OS` |
| `krok` | co ile metrów stawiać łatę (`3`, `6`, `1`, `0` = tylko końce) |

Odpowiedź zawiera `dlugosc_osiowa_m` i `dlugosc_rury_m` (po odjęciu promieni
studni), oba warianty spadku oraz tabelę punktów:

```json
{"odleglosc_m": 6.0, "rzedna_dna": 44.219, "rzedna_laty": 44.719,
 "odczyt": 2.063, "wykonalny": true, "opis": ""}
```

`wykonalny: false` oznacza odczyt poza łatą (poniżej 0 albo powyżej 4 m).

---

## Konta i zadania

| Endpoint | Zwraca |
|---|---|
| `GET/POST /login` | ekran logowania |
| `GET /logout` | wylogowanie |
| `GET /panel/uzytkownicy` | panel kont (tylko ADMIN) |
| `POST /panel/uzytkownicy/dodaj` | nowe konto |
| `POST /panel/uzytkownicy/<id>/haslo` | reset hasła |
| `POST /panel/uzytkownicy/<id>/przelacz` | włącz/wyłącz konto |
| `POST /panel/uzytkownicy/<id>/rola` | zmiana roli |
| `GET /zadania` · `GET /api/zadania?zakres=` | lista zadań |
| `POST /zadania/dodaj` · `/zadania/<id>/status` · `/zadania/<id>/usun` | operacje na zadaniach |

**Wszystkie endpointy wymagają zalogowania** poza `/login`, `/static/…`,
`/api/zdrowie`, `/service-worker.js` i `/offline`. Bez sesji zwracają `302`
na `/login`.

Dwa ostatnie są otwarte celowo: przeglądarka pobiera skrypt offline przed
zalogowaniem, a przy braku sieci użytkownik ma zobaczyć informację o zasięgu,
a nie ekran logowania, którego i tak nie da się wysłać.

---

## Widoki HTML

| Ścieżka | Widok |
|---|---|
| `/` | pulpit |
| `/szukaj?q=D155` | **wyszukiwarka — główny widok roboczy** |
| `/obiekt/<kod>` | karta obiektu |
| `/odcinki`, `/obiekty`, `/profile` | tabele przeglądowe |
| `/profil/<id>` | profil podłużny z rysunkiem |
| `/niwelator/` | kalkulator niwelacyjny |
| `/niwelator/ciag-rur` | **tyczenie ciągu rur — odczyt na łacie** |
| `/mapa` | **przeglądarka planów: zoom, warstwy, skala, georeferencja** |
| `/zadania` | zadania globalne i przypisane |
| `/panel/uzytkownicy` | konta (tylko ADMIN) |
| `/wykonanie` | **dziennik wykonawczy — rzędne z wykopu** |
| `/postep` | stan odcinków i postęp całej sieci |
| `/raporty` | raporty dzienne brygady |
| `/qr` | arkusz kodów QR na studnie |
| `/odcinek/<od>/<do>/karta` | karta odcinka do druku (A4) |
| `/osnowa`, `/materialy`, `/importy` | osnowa, materiały, historia importów |
