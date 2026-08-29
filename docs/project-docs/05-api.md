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
| `GET /api/importy/<id>/ostrzezenia` | pełna lista rozbieżności |
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
| `GET /mapa/obiekt/<kod>.png` | wycinek wokół obiektu z zaznaczeniem |
| `GET /mapa/odcinek/<od>/<do>.png` | wycinek obejmujący oba końce |
| `POST /api/mapa/pozycja` | zapis ręcznie wskazanej pozycji |
| `DELETE /api/mapa/pozycja/<kod>` | usunięcie wskazania |

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

**Wszystkie endpointy wymagają zalogowania** poza `/login`, `/static/…`
i `/api/zdrowie`. Bez sesji zwracają `302` na `/login`.

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
| `/mapa` | przeglądarka planów i wskazywanie pozycji |
| `/zadania` | zadania globalne i przypisane |
| `/panel/uzytkownicy` | konta (tylko ADMIN) |
| `/osnowa`, `/materialy`, `/importy` | osnowa, materiały, historia importów |
