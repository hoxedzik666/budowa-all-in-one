# `Profile Scalone.pdf` — jak rozumiem ten plik

> Zapis tego, co odczytałem z rysunku, w kolejności od struktury arkusza do
> pojedynczej liczby. Wszystkie liczby w przykładach są prawdziwe — wzięte
> z pliku i sprawdzone.

---

## 0. Co to za dokumentacja

Rysunki profili podłużnych kanalizacji dla zadania:

> **„Budowa obwodnicy miejscowości Krosno Odrzańskie w ciągu drogi krajowej nr 29"**
> Inwestor: Skarb Państwa — GDDKiA, Oddział w Zielonej Górze
> Wykonawca: POLAQUA Sp. z o.o.
> Jednostka projektowa: Highway Sp. z o.o., Gdańsk

Plik wygenerowany programem **„P.S.I./EPI-Graf, Generator rysunkowy Profil
Koordynator 8.0"**. To istotne: rysunek jest **generowany maszynowo**, więc ma
sztywną, powtarzalną strukturę — i właśnie dlatego da się go czytać programowo
z dużą pewnością.

**13 arkuszy**, każdy to poziomy pas o szerokości 4800–7200 pt i wysokości
840–1690 pt (czyli formaty rzędu A0 rozwiniętego wzdłuż). Skala pozioma **1:500**,
pionowa **1:100** — typowe przewyższenie profilu 5×.

---

## 1. Struktura arkusza

Każdy arkusz dzieli się poziomo na dwie części:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   OBSZAR RYSUNKU — linie terenu, linia kanału, opisy       │  ← góra
│   obiektów pisane PIONOWO, adnotacje o włączeniach          │
│                                                             │
├──────────────────┬──────────────────────────────────────────┤
│ OZNACZENIE PROF. │                                          │
│ POZIOM PORÓWN.   │                                          │
│ RZĘDNA TER.PROJ. │   TABELA DANYCH                          │  ← dół
│ RZĘDNA TER.ISTN. │   wartości w kolumnach pod węzłami       │
│ RZĘDNA DNA KAN.  │                                          │
│ ZAGŁĘB. DNA KAN. │                                          │
│ SPADKI, DŁUGOŚCI │                                          │
│ ŚREDNICA, MATER. │                                          │
│ ODLEGŁOŚCI       │                                          │
│ HEKTOMETRY       │                                          │
└──────────────────┴──────────────────────────────────────────┘
   legenda pasm         dane, ciągnące się w prawo na całą szerokość
```

**Legenda pasm występuje dokładnie raz na stronę** (sprawdziłem na wszystkich 13).
Jej pozycje `y` wyznaczają, które pasmo jest które — to jest kotwica całego
odczytu.

### Kluczowa obserwacja: jeden arkusz = wiele profili

Arkusz nie jest jednym profilem. To **wiele niezależnych profili ustawionych
obok siebie** wzdłuż osi X, dzielących wspólne pasma. Strona 6 ma ich **35**,
strona 13 — **61**.

Każdy taki blok ma przy swojej lewej krawędzi **własny nagłówek**:

```
D155           ← nazwa profilu
70.00m         ← poziom porównawczy
n.p.m.
```

Napis **`n.p.m.` jest jedynym pewnym znacznikiem początku bloku.** Nie można
kotwiczyć się na samej liczbie z „m", bo tak samo wygląda długość odcinka
w paśmie SPADKI (np. `20.5m`) — na tym się na początku przewróciłem.

Wyjątek: **strona 5** ma jeden profil na cały arkusz i wtedy nagłówek jest
wpisany w wiersz legendy (`75.00 m n.p.m.` jako jeden napis).

---

## 2. Orientacja tekstu — to nie jest szczegół

W PDF-ie tekst występuje w dwóch orientacjach i **ta różnica niesie znaczenie**:

| Orientacja | Co zawiera |
|---|---|
| **PIONOWO** (obrót 90°, `dir = (0,−1)`) | wartości należące do **WĘZŁA** — rzędne, zagłębienie, pikietaż, opis obiektu |
| **POZIOMO** (`dir = (1,0)`) | wartości należące do **ODCINKA** — spadek, średnica, długość, odległość cząstkowa; oraz kody obiektów i nagłówki bloków |

Czyli: **pionowo = punkt, poziomo = to, co między punktami.** Ta reguła sama
w sobie rozdziela dane obiektów od danych odcinków.

Dodatkowo: fonty są typu `Type0/CIDFontType2` z poprawnymi mapami `ToUnicode`,
więc polskie znaki (`Ę Ł Ś Ó`), `Ø` i `°` czytają się bezbłędnie —
pod warunkiem użycia biblioteki, która te mapy honoruje (PyMuPDF).
`pdftotext` z pakietu xpdf gubi diakrytykę i nie ma trybu współrzędnych.

---

## 3. Przykład rozłożony na czynniki — profil `D155` (strona 6)

To jest ten przypadek, o który pytałeś. Surowe pozycje z PDF-u:

```
pasmo                 x=2734.8 (Wyl101)      między            x=2852.9 (D155)
─────────────────────────────────────────────────────────────────────────────
OPIS (pion)           "Wylot"                                  "Studnia z piaskownikiem
                                                                DN1500, Rz.d.=82.26"
RZĘDNA TERENU PROJ.   82.70                                    83.81
RZĘDNA TERENU ISTN.   83.57                                    83.64
RZĘDNA DNA KANAŁU     82.70                                    82.76
ZAGŁĘBIENIE           0.00                                     1.05
SPADKI, DŁUGOŚCI                             0.3%   20.5m
ŚREDNICA, MATERIAŁ                           Ø500
ODLEGŁOŚCI            0.00                   20.5             20.31
HEKTOMETRY            Wyl101                                   D155
```

Odległość na papierze między kolumnami: 2852.9 − 2734.8 = **118.1 pt**.
118.1 pt ≈ 41.6 mm, przy skali 1:500 daje **20.8 m** — zgadza się z podaną
długością 20.5 m. To niezależne potwierdzenie, że dobrze zidentyfikowałem
kolumny.

### Interpretacja

To są **trzy osobne byty**, każdy ze swoimi danymi:

**① OBIEKT `Wyl101` — wylot**
```
typ                          WYLOT
rzędna dna kanału            82.70 m n.p.m.
rzędna terenu istniejącego   83.57
rzędna terenu projektowanego 82.70
zagłębienie                  0.00 m     (dno na poziomie terenu — bo to wylot)
pikietaż w profilu           0.00 m     (początek)
opis                         "Wylot"
```

**② OBIEKT `D155` — studnia z piaskownikiem**
```
typ                          STUDNIA
średnica studni              DN1500
rzędna dna kanału            82.76 m n.p.m.   ← spód rury
rzędna dna studni (Rz.d.)    82.26 m n.p.m.   ← dno piaskownika, 0.50 m niżej
rzędna terenu istniejącego   83.64
rzędna terenu projektowanego 83.81
zagłębienie                  1.05 m           (83.81 − 82.76 ✓)
głębokość wykopu             1.55 m           (83.81 − 82.26)
pikietaż w profilu           20.31 m
```

**③ ODCINEK `Wyl101 – D155`**
```
od                Wyl101
do                D155
długość           20.5 m
średnica          Ø500 mm
spadek            0.3%  =  3‰
rzędna dna od     82.70
rzędna dna do     82.76
kontrola:         20.5 × 0.003 = 0.0615 m ≈ 82.76 − 82.70 = 0.06  ✓
```

Zwróć uwagę: rzędna dna **rośnie** od `Wyl101` do `D155`. To nie błąd — profil
jest rysowany **od wylotu w górę zlewni**, a woda płynie w przeciwną stronę
(z `D155` do `Wyl101`). Kierunek rysunku zapisuję osobno, a spadki porównuję
co do wartości bezwzględnej.

---

## 4. Jak czytam każde pasmo

### `HEKTOMETRY` — kody obiektów (punkty trasy)
Dolne pasmo. Poziome napisy pod kolumnami — to **oznaczenia punktów trasy**
(w arkuszu Excela nazwane `PZ — Oznaczenie punktu trasy`). To one wyznaczają
pozycje `x` wszystkich kolumn.

### `ODLEGŁOŚCI` — pikietaż i odległości cząstkowe
Dwie różne rzeczy w jednym paśmie, rozróżniane orientacją:
- **pionowo, pod węzłem** → pikietaż narastająco od początku profilu
  (`0.00`, `20.31`),
- **poziomo, między węzłami** → odległość cząstkowa (`20.5`).

Pikietaż w obrębie jednego profilu **zawsze rośnie**. Wykorzystuję to jako
zabezpieczenie: gdy wartość spada, znaczy że zaczął się kolejny profil, którego
nagłówka nie udało się wykryć — i dzielę blok w tym miejscu.

### `ŚREDNICA, MATERIAŁ`
Poziomo, między węzłami: `Ø500`, `Ø200 L=21.0m`, `Ø600 L=25.5m`.
Zapis `L=…m` bywa alternatywnym źródłem długości odcinka.

### `SPADKI, DŁUGOŚCI`
Poziomo, między węzłami. Dwa rodzaje napisów:
- `0.3%`, `9%`, `0%`, `8.8%` → **spadek** (w bazie zamieniam na promile),
- `20.5m`, `78.5m` → **długość** odcinka.

### `ZAGŁĘBIENIE DNA KANAŁU`, `RZĘDNA DNA KANAŁU`, `RZĘDNA TERENU ISTN./PROJ.`
Pionowo, po jednej wartości na węzeł. Powiązane niezmiennikiem
`zagłębienie = teren proj. − dno`.

### `POZIOM PORÓWNAWCZY`
`30.00m n.p.m.`, `70.00m n.p.m.`, `75.00m n.p.m.` — to **baza rysunku**, czyli
dolna krawędź obszaru wykresu, a **nie dana projektowa**. Zapisuję ją dla
wierności odwzorowania, ale nie liczę z niej niczego.

### `OZNACZENIE PROFILU:`
Nazwa bloku. Na stronie 6 kolejno: `Wyl84`, `Wyl85`, …, `Wp63`, `Wp64`,
**`D155`**, `Wp65`, `Wp66`, … Nazwa bierze się zwykle od **końcowego** obiektu
profilu, nie od początkowego — profil zawierający `Wyl101 → D155` nazywa się
`D155`.

---

## 5. Opisy obiektów a adnotacje rysunkowe — pułapka z `Rz.d.=`

Nad tabelą, pionowo, biegną dwa różne rodzaje napisów. **Oba zawierają `Rz.d.=`
i oba oznaczają co innego.**

| Rodzaj | Przykład | Co znaczy `Rz.d.=` |
|---|---|---|
| **opis obiektu** | `Studnia z piaskownikiem DN1500, Rz.d.=82.26` | rzędna **dna studni** |
| **adnotacja** | `Proj. włączenie kanału Wp133 Ø400, Rz.d.=43.46` | rzędna **wlotu przyłącza** |
| **adnotacja** | `Skrzyżowanie z proj. KD sieci Ø300, Rz.d.=81.00` | rzędna **obcej sieci** |

Na początku mieszałem te dwa i dostawałem absurdy w rodzaju „dno studni powyżej
dna kanału". Rozdzielam je po słowach kluczowych: napisy zaczynające się od
`Proj. włączenie`, `Skrzyżowanie`, `Istn.` to adnotacje → trafiają do tabeli
połączeń, nie do opisu obiektu. Po tej poprawce ta klasa błędów zniknęła
całkowicie.

Adnotacje niosą też **kąty**: `115°`, `196°(K1)`, `253°(K2)` — kierunek
włączenia, gdzie `(K1)`/`(K2)` wskazuje, którego kanału dotyczy.

---

## 6. Typy obiektów, jakie znalazłem

Twoja legenda plus to, co doszło z pliku:

| Prefiks | Znaczenie | Ile w bazie |
|---|---|---|
| `Wyl` | **wylot** | 420 |
| `Wp` | **wpust** deszczowy | 440 |
| `D` | **studnia** (rewizyjna / z piaskownikiem) | 158 |
| `SEP` | **separator** substancji ropopochodnych | 9 |
| `O` | **osadnik** | 13 |
| `Tr` | **trójnik** — *nie było w legendzie* | 1 |
| `Ł` | **łuk** / załamanie trasy — *nie było w legendzie* | 3 |
| `KT` | **węzeł kanału tłocznego** — *nie było w legendzie* | 15 |

Razem **1059 obiektów**.

Typ rozpoznaję **najpierw z opisu projektanta**, dopiero potem z prefiksu kodu —
bo opis jest jednoznaczny („Studnia betonowa DN 1200", „Osadnik", „Separator"),
a prefiks bywa mylący.

### Rzeczy, które wymagały rozstrzygnięcia

- **`S.S.S.Wp253`, `S.S.S.Wyl256`** — zgodnie z Twoją odpowiedzią traktuję
  `S.S.S.` jako artefakt nakładających się napisów. Prefiks obcinam; w bazie
  nie ma ani jednego kodu z `S.S.S.` (sprawdzane testem).
- **`KT15=D139`** — zapis równości: to jeden obiekt o dwóch oznaczeniach.
  Główny kod `KT15`, `D139` zapisuję jako alias.
- **`ściek sk.`** — ściek skarpowy, element odwodnienia powierzchniowego.
  Nie jest węzłem kanału; nie tworzę z niego obiektu.
- **Blok tytułowy** (`Podpis:`, `Nr uprawnień:`, nazwiska projektantów) leży
  w tym samym paśmie `y` co kody obiektów. Odrzucam go wzorcem kodu —
  116 takich napisów w całym pliku, żaden nie przeszedł.

---

## 7. Dwa rodzaje profili — grawitacja i ciśnienie

**Strona 5 jest inna niż pozostałe.** Zamiast:
```
RZĘDNA DNA KANAŁU  /  ZAGŁĘBIENIE DNA KANAŁU
```
ma:
```
RZĘDNA OSI PRZEWODU  /  ZAGŁĘBIENIE OSI PRZEWODU
```
a opisy używają `Rz.o.=` zamiast `Rz.d.=`. To **kanał tłoczny** (ciśnieniowy),
profile `KT1`…`KT15`. W rurociągu ciśnieniowym odniesieniem jest **oś rury**,
nie jej dno — bo woda wypełnia cały przekrój i spadek dna nie ma znaczenia
hydraulicznego.

W bazie rozróżniam to jawnie: `profile.branza` ∈ {`KD`, `KT`} oraz
`profile.typ_odniesienia` ∈ {`DNO_KANALU`, `OS_PRZEWODU`}.

Strona 9 to w większości ścieki skarpowe — element odwodnienia powierzchniowego,
opisywany długością i rzędną w nawiasie.

---

## 8. Co finalnie wyszło z pliku

```
13 arkuszy → 465 profili → 1059 obiektów → 649 odcinków → 7 439,5 m sieci
```

**Rury wg średnicy:**

| Ø [mm] | odcinków | długość [m] |
|---|---|---|
| 200 | 348 | 2 157,4 |
| 250 | 32 | 206,4 |
| 300 | 3 | 103,0 |
| 400 | 39 | 1 205,0 |
| 500 | 15 | 554,5 |
| 600 | 8 | 302,0 |
| 1000 | 1 | 16,0 |

**Spadki:** dominują strome przykanaliki (283 odcinki w przedziale 30–100‰ —
to króćce od wpustów), kanały główne mieszczą się w 1–30‰.

**Skrajne zagłębienia:**
- najgłębiej: `D145` — 5,63 m (teren 66,84 / dno 61,21)
- najpłycej: `Wyl104` — **−0,40 m** (wylot wystający ze skarpy)

**Kompletność:**
- 648 z 649 odcinków ma długość,
- 446 ma średnicę, 556 ma spadek, **412 ma komplet** (długość + Ø + spadek),
- 1057 z 1059 obiektów ma rzędną dna, **wszystkie 1059** mają rzędną terenu
  projektowanego,
- 621 obiektów ma rzędną dna studni (`Rz.d.`).

Braki nie są błędem parsera — na rysunku po prostu nie każdy odcinek ma
wypisaną wprost średnicę czy spadek (dziedziczy je z sąsiedztwa albo z opisu
zbiorczego).

---

## 9. Kontrola jakości — co sprawdzam przy imporcie

Trzy niezależne testy, wszystkie **raportowane, nie ukrywane**:

**① Niezmiennik zagłębienia** (na węźle)
```
zagłębienie = rzędna terenu proj. − rzędna dna     (tolerancja 1,5 cm)
```
Używam go podwójnie: jako walidatora **i** jako reguły rozstrzygającej.
Gdy studnia ma kilka wlotów, w paśmie rzędnych jest więcej liczb niż węzłów —
wtedy wybieram tę trójkę (teren, dno, zagłębienie), która niezmiennik spełnia.
Ta jedna zmiana zmniejszyła liczbę ostrzeżeń ze 217 do 90.

**② Zgodność spadku z rzędnymi** (na odcinku)
```
|rzędna_od − rzędna_do| / długość × 1000  ≈  spadek z rysunku
```

**③ Kontrola krzyżowa z `Materiał.xlsx`**
Rzędne z arkusza porównuję z odczytanymi z PDF. **PDF jest źródłem geometrii** —
przy rozbieżności nie nadpisuję, tylko raportuję.

### Wynik

- **67 ostrzeżeń** z samego PDF na ~1760 sprawdzeń (3,8%),
- **41 rozbieżności** PDF ↔ XLSX,
- **0 nowych obiektów** z XLSX — czyli **każdy obiekt z arkusza został wcześniej
  znaleziony w PDF**. To najmocniejsze potwierdzenie, że odczyt rysunku jest
  kompletny.

Największe rozbieżności (np. `Wp428`: teren 53,79 wg PDF vs 60,82 wg XLSX,
różnica **7 m**) to miejsca do sprawdzenia **w dokumentacji** — jedno ze źródeł
jest nieaktualne. Narzędzie ich nie rozstrzyga, tylko wskazuje.

Pozostałe ostrzeżenia o spadkach dotyczą prawie wyłącznie studni z rurami
wchodzącymi na różnych rzędnych — to rzeczywistość, nie błąd odczytu. Dlatego
rzędne trzymam **podwójnie**: kanoniczną przy obiekcie (najniższą = odpływ)
i osobno tę odczytaną na każdym profilu.

---

## 10. Pytania, które zostają otwarte

1. **Układ wysokościowy osnowy** — `!!_DK29_osnowa_ok_v1.txt` nie podaje, czy to
   Kronsztadt'86 czy PL-EVRF2007-NH. Różnica ~15 cm.
2. **`Wo287`, `Ws7`, `Ws8`** — pojedyncze wystąpienia prefiksów spoza legendy.
   Zaimportowane, ale bez pewnej klasyfikacji typu.
3. **Rozbieżności PDF ↔ XLSX** — 41 sztuk, w tym cztery powyżej 2 m
   (`Wp428`, `Wp217`, `Wp218`, `Wp219`). Które źródło jest aktualne?

Wszystkie trzy są widoczne w aplikacji w zakładce **Importy**.

---

## Powiązane

- `01-niwelacja-podstawy.md` — reper, rzędne, niwelator, wzory
- `03-model-danych.md` — schemat bazy i reguły mapowania
- Kod: `app/services/pdf_profile_parser.py`, testy: `tests/test_parser_profili.py`
