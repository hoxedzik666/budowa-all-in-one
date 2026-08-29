# Model danych — schemat bazy i reguły mapowania

> Jak dokumentacja projektowa trafia do PostgreSQL i dlaczego akurat tak.

---

## 1. Dlaczego PostgreSQL

- **Rekurencyjne CTE** — sieć kanalizacyjna to graf. Pytanie „co spływa do
  `Wyl101`?" to przejście grafu w górę zlewni; w Postgresie to jedno zapytanie
  `WITH RECURSIVE`.
- **`NUMERIC`, nie `float`** — rzędne to setne części metra i muszą się sumować
  bez dryfu. Wszystkie rzędne: `NUMERIC(8,3)`.
- **`JSONB`** — surowy odczyt z parsera (`surowe`, `bbox`) i lista ostrzeżeń
  importu. Pozwala odpowiedzieć na pytanie „skąd wzięła się ta liczba" bez
  wracania do PDF-u, a przy tym jest indeksowalny.
- Dojrzałe **PostGIS**, gdy dojdą plany sytuacyjne i współrzędne PL-2000.

---

## 2. Schemat

```
sheet ──< profile ──< object_occurrence >── network_object ──< connection
                 └──< segment >───────────┘
survey_point        material_item        import_run
```

### `sheet` — arkusz PDF
Strona rysunku: numer, wymiary MediaBox, branża (`KD` / `KT`).
Klucz naturalny: `(plik, nr_strony)`.

### `profile` — profil podłużny
Jeden blok rysunkowy. `oznaczenie` (np. `D155`, `KT1`), `poziom_porownawczy`,
`dlugosc_calkowita_m`, `blok_index` (pozycja na arkuszu) oraz dwa pola
rozróżniające rodzaj sieci:

| pole | wartości | znaczenie |
|---|---|---|
| `branza` | `KD` / `KT` / `SCIEK_SKARPOWY` | rodzaj sieci |
| `typ_odniesienia` | `DNO_KANALU` / `OS_PRZEWODU` | do czego odnoszą się rzędne |

### `network_object` — OBIEKT (węzeł sieci)
**Kanoniczny, unikalny po `kod`.** Jeden `D155` w całej bazie, niezależnie od
tego, na ilu profilach się pojawia.

```
kod                    UNIQUE   'D155'
typ                    enum     WYLOT|STUDNIA|WPUST|SEPARATOR|OSADNIK|
                                TROJNIK|LUK|WEZEL_KT|SCIEK_SKARPOWY|INNY
rzedna_dna_kanalu      NUMERIC  82.760   ← spód rury (albo oś, dla KT)
rzedna_dna_studni      NUMERIC  82.260   ← 'Rz.d.' z opisu — do tego kopiemy
rzedna_terenu_istn     NUMERIC  83.640
rzedna_terenu_proj     NUMERIC  83.810
zaglebienie            NUMERIC  1.050    ← teren proj. − dno (może być ujemne)
rzedna_dna_rowu        NUMERIC           ← odbiornik przy wylocie
dn_mm                  INT      500      ← średnica króćca
srednica_studni_mm     INT      1500     ← DN studni
status                 enum     PROJEKT|WYTYCZONY|W_TRAKCIE|WYKONANY|ODEBRANY
zrodlo                 enum     PDF_PROFIL|XLSX_MATERIAL|TXT_OSNOWA|RECZNE
surowe                 JSONB
```

Właściwość wyliczana `glebokosc_wykopu = rzedna_terenu_proj − rzedna_dna_studni`
(z zejściem na `rzedna_dna_kanalu`, gdy studnia nie ma osadnika).

### `object_occurrence` — wystąpienie obiektu na profilu
**Rozwiązuje problem, którego nie da się obejść inaczej:** studnia ma tyle
rzędnych dna, ile wchodzi do niej rur, a każdy profil pokazuje tę „swoją".

```
profil_id, obiekt_id, kolejnosc
hektometr              ← pikietaż w tym profilu
rzedna_dna             ← rzędna odczytana NA TYM profilu
zaglebienie, rzedna_terenu_proj, rzedna_terenu_istn, opis
bbox                   JSONB — pozycja na rysunku, do audytu
```

**Reguła:** `network_object.rzedna_dna_kanalu` = **minimum** ze wszystkich
wystąpień (rzędna odpływu — najniższa rura). Pozostałe zostają w wystąpieniach
i w `connection`. Dzięki temu nic nie ginie, a widok obiektu pokazuje
jednoznaczną liczbę.

### `segment` — ODCINEK
Rura między dwoma obiektami. Podstawowa jednostka robocza brygady.

```
profil_id, obiekt_od_id, obiekt_do_id, kolejnosc
dlugosc_m         NUMERIC  20.50
dn_mm             INT      500
spadek_promile    NUMERIC  3.000    ← procenty z rysunku ×10
rzedna_dna_od     NUMERIC  82.700
rzedna_dna_do     NUMERIC  82.760
material, status, surowe JSONB
UNIQUE (profil_id, obiekt_od_id, obiekt_do_id)
CHECK  (obiekt_od_id <> obiekt_do_id)
```

Właściwości wyliczane: `spadek_procent`, `spadek_wyliczony_promile`
(z rzędnych — do kontroli tego z rysunku).

### `connection` — włączenia i przyłącza
Dwa źródła w jednej tabeli:
- z **PDF**: adnotacje `Proj. włączenie kanału Wp133 Ø400, Rz.d.=43.46`,
  kąty `196°(K1)` — 102 rekordy;
- z **XLSX**: kolumna `Odbiornik` z arkusza *Wpusty* (jawny graf: `Wp133 → D6`)
  oraz pary `D1/RD1`, `D2/RD2` z arkusza *Studnie* — 780 rekordów.

### `survey_point` — osnowa / repery
`nazwa`, `x`, `y`, `h`, `uklad` (`PL-2000/5`). 151 punktów.

### `material_item` — gospodarka materiałowa
Arkusz `RURY`: pozycja, ilość projektowa, długość sztuki, ile dojechało,
data dostawy, numer WZ. Właściwość `brakuje_m`.

### `import_run` — audyt
Każdy przebieg importu: plik, `sha256`, statystyki i **pełna lista ostrzeżeń**
w `JSONB`. To jest miejsce, w którym widać, czego nie dało się pogodzić.

---

## 3. Reguły mapowania PDF → baza

| Na rysunku | W bazie |
|---|---|
| blok z nagłówkiem `nazwa` + `n.p.m.` | `profile` |
| kod w dolnym paśmie (`Wyl101`) | `network_object.kod` + `object_occurrence` |
| pionowa liczba w paśmie `RZĘDNA DNA KANAŁU` | `object_occurrence.rzedna_dna` |
| `Rz.d.=82.26` **w opisie obiektu** | `network_object.rzedna_dna_studni` |
| `Rz.d.=43.46` **w adnotacji o włączeniu** | `connection.rzedna` |
| `DN1500` w opisie | `srednica_studni_mm` |
| `Ø500` między węzłami | `segment.dn_mm` |
| `0.3%` między węzłami | `segment.spadek_promile = 3.0` |
| `20.5m` w paśmie SPADKI | `segment.dlugosc_m` |
| pionowa liczba w paśmie ODLEGŁOŚCI | `object_occurrence.hektometr` |
| `RZĘDNA OSI PRZEWODU` w legendzie | `profile.typ_odniesienia = OS_PRZEWODU` |
| `KT15=D139` | `kod = 'KT15'`, `uwagi = 'alias: D139'` |
| `S.S.S.Wp253` | `kod = 'Wp253'` (prefiks obcięty) |

### Normalizacja kodu
```
S.S.S.Wp253  →  Wp253          (obcięcie artefaktu nakładających się napisów)
KT15=D139    →  KT15 + alias   (zapis równości dwóch oznaczeń)
Wyl 101      →  Wyl101         (usunięcie spacji)
Podpis:      →  odrzucone      (blok tytułowy w tym samym paśmie y)
```

### Rozstrzyganie węzłów z wieloma wlotami
Gdy w paśmie jest więcej liczb niż węzłów, wybieram trójkę
(teren proj., dno, zagłębienie) minimalizującą
`|teren − dno − zagłębienie|`, akceptując przy progu **1,5 cm**.
Nadmiarowe rzędne dna → `connection` jako dodatkowe wloty.

---

## 4. Reguły mapowania XLSX → baza

**PDF jest źródłem geometrii. XLSX uzupełnia braki i waliduje.**

```
wartość z XLSX, gdy pole w bazie puste   →  uzupełnij
wartość z XLSX różna o > 2 cm            →  NIE nadpisuj, zapisz rozbieżność
```

| Arkusz | Kolumny → pola |
|---|---|
| **Studnie** | `PZ`→kod, `Dn`→`srednica_studni_mm` (m→mm), `RTp`→teren proj., `Rz.d.`→dno studni, `D1/RD1`, `D2/RD2`, `Dw1/Rw1`, `Dw2/Rw2`→`connection` |
| **Wpusty** | `PZ`→kod, `RTp`, `Rz.d.`, **`Odbiornik`→`connection` kierunek `ODPLYW`** |
| **Wyloty** | `PZ`→kod, `Dn`→`dn_mm`, `Rz.d.`→dno kanału, `Rz. Dna rowu/zbiornika`, `Uwagi` (typ umocnienia KPED) |
| **RURY** | `OPIS POZYCJI`, `ILOŚCI [M]`, `DŁUGOŚĆ`, `DOJECHAŁO`, `DATA DOSTAWY`, `WZ` → `material_item` |

Kod obiektu bywa w kolumnie `A` zamiast `B` — czytam obie.

---

## 5. Stan po imporcie

```
arkusze                13
profile               465
obiekty              1059      (WPUST 440, WYLOT 420, STUDNIA 158,
wystąpienia          1114       WEZEL_KT 15, OSADNIK 13, SEPARATOR 9,
odcinki               649       LUK 3, TROJNIK 1)
połączenia            882      (PDF 102 + XLSX 780)
punkty osnowy         151
pozycje materiałowe    32

łączna długość sieci  7 439,5 m
```

**Ostrzeżenia:** 67 z PDF, 41 rozbieżności PDF↔XLSX.
**0 nowych obiektów z XLSX** — każdy obiekt z arkusza był już znaleziony w PDF.

---

## 6. Przykładowe zapytania

**Odcinek i oba jego końce**
```sql
SELECT a.kod AS od, b.kod AS "do", s.dlugosc_m, s.dn_mm,
       s.spadek_promile, s.rzedna_dna_od, s.rzedna_dna_do
FROM segment s
JOIN network_object a ON a.id = s.obiekt_od_id
JOIN network_object b ON b.id = s.obiekt_do_id
WHERE a.kod = 'Wyl101' AND b.kod = 'D155';
```

**Studnie głębsze niż 4 m — planowanie szalunków**
```sql
SELECT kod, rzedna_terenu_proj, rzedna_dna_studni,
       rzedna_terenu_proj - rzedna_dna_studni AS glebokosc
FROM network_object
WHERE typ = 'STUDNIA' AND rzedna_dna_studni IS NOT NULL
ORDER BY glebokosc DESC NULLS LAST
LIMIT 20;
```

**Co spływa do danego wylotu — przejście grafu w górę zlewni**
```sql
WITH RECURSIVE zlewnia AS (
    SELECT s.id, s.obiekt_od_id, s.obiekt_do_id, s.dlugosc_m, 1 AS poziom
    FROM segment s
    JOIN network_object b ON b.id = s.obiekt_do_id
    WHERE b.kod = 'D155'
  UNION ALL
    SELECT s.id, s.obiekt_od_id, s.obiekt_do_id, s.dlugosc_m, z.poziom + 1
    FROM segment s
    JOIN zlewnia z ON s.obiekt_do_id = z.obiekt_od_id
    WHERE z.poziom < 50
)
SELECT poziom, a.kod AS od, b.kod AS "do", dlugosc_m
FROM zlewnia
JOIN network_object a ON a.id = obiekt_od_id
JOIN network_object b ON b.id = obiekt_do_id
ORDER BY poziom;
```

**Odcinki, gdzie spadek z rysunku nie zgadza się z rzędnymi**
```sql
SELECT a.kod, b.kod, s.dlugosc_m, s.spadek_promile,
       ABS(s.rzedna_dna_od - s.rzedna_dna_do) / s.dlugosc_m * 1000 AS z_rzednych
FROM segment s
JOIN network_object a ON a.id = s.obiekt_od_id
JOIN network_object b ON b.id = s.obiekt_do_id
WHERE s.dlugosc_m > 0 AND s.spadek_promile IS NOT NULL
  AND ABS(ABS(s.rzedna_dna_od - s.rzedna_dna_do) / s.dlugosc_m * 1000
          - s.spadek_promile) > 1
ORDER BY 5 DESC;
```

---

## 7. Uruchomienie

```bash
docker compose up -d --build
docker compose exec web python -m flask import-wszystko
docker compose exec web python -m pytest -q
```

- aplikacja: <http://localhost:8000>
- Adminer (podgląd bazy): <http://localhost:8080> — serwer `db`, użytkownik `budowa`

Komendy pojedyncze: `flask import-osnowa`, `flask import-profile`,
`flask import-xlsx`, `flask statystyki`,
`flask pokaz-odcinek Wyl101 D155`.

---

## Powiązane

- `01-niwelacja-podstawy.md` — reper, rzędne, niwelator, wzory
- `02-analiza-profile-scalone.md` — jak czytam rysunek
- Kod: `app/models/`, `app/services/importer.py`, `app/services/xlsx_importer.py`
