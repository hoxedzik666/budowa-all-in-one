# Audyt branżowy — odwodnienie obwodnicy DK29

> Kontrola dokumentacji i danych pod kątem **norm i praktyki projektowania odwodnienia
> drogowego**. Uzupełnia [`project-docs/11-audyt-danych.md`](project-docs/11-audyt-danych.md),
> który audytuje przepływ danych (duplikaty importu, niezmienniki, wydajność) i **świadomie
> nie dotyka poprawności branżowej**.
>
> Każda liczba pochodzi z [`scripts/audyt_branzowy.py`](../scripts/audyt_branzowy.py) —
> skryptu read-only na bibliotece standardowej, uruchamianego bez Flaska i bez Dockera.

```bash
python3 scripts/audyt_branzowy.py                       # cały raport
python3 scripts/audyt_branzowy.py --sekcja spadki       # jedna grupa
python3 scripts/audyt_branzowy.py --limit 0             # pełne listy
```

---

## 1. Jak czytać ten raport

Trzy kategorie. **Mieszanie ich jest głównym błędem raportowania o tym projekcie** — bo
prowadzi albo do poprawiania dokumentacji przez program, albo do ignorowania wszystkiego jako
„szumu z parsera".

| | Kategoria | Co znaczy | Kto to zamyka |
|---|---|---|---|
| **[O]** | błąd odczytu | parser albo importer przekłamał dokumentację | programista |
| **[B]** | brak danych | rysunek lub arkusz tego nie podaje | projektant / wykonawca |
| **[P]** | do wyjaśnienia | dane odczytane wiernie, ale odbiegają od normy | projektant |

**Ustaleń [P] nie rozstrzygamy.** Wskazujemy miejsce i regułę. Zgadywanie „poprawnych"
wartości jest w tym repozytorium zakazane wprost (`11-audyt-danych.md`, A5) i ten raport
tego nie zmienia.

### Streszczenie

| # | Ustalenie | Skala | Kat. | Waga |
|---|---|---|---|---|
| B1 | Układ wysokościowy osnowy niezadeklarowany | 151 punktów, ryzyko 0,165 m | [B] | **krytyczna** |
| B2 | Kanał tłoczny bez przepompowni i bez odbiornika | 15 obiektów, 680 m | [O] | **krytyczna** |
| B3 | Przykrycie poniżej strefy przemarzania | 55 węzłów (z 126) | [P] | wysoka |
| B4 | Zestawienie materiałowe liczone podwójnie | 10 299,8 m zamiast ≈5 150 m | [O] | wysoka |
| B5 | Klasa SN nigdzie nie dociera do odcinka | 0 z 649 odcinków | [B] | wysoka |
| B6 | Odcinki poniżej spadku minimalnego | 39 odcinków | [P] | wysoka |
| B7 | Odcinki o spadku absurdalnym (błąd odczytu) | 55 odcinków > 100‰ | [O] | wysoka |
| B8 | Wyloty bez wyniesienia nad dno rowu | 41 wylotów | [P] | średnia |
| B9 | Sieć bez współrzędnych — „mapy z reperami" nie ma | 0 z 1059 obiektów | [B] | średnia |
| B10 | Rozstaw studni ponad typowy limit | 10 odcinków, do 175 m | [P] | średnia |
| B11 | Brak średnicy na 39 % długości sieci | 203 odcinki / 2 895,2 m | [B] | średnia |
| B12 | Obiekty z arkusza nieobecne w bazie | `K1`, `Sch1`, `Sch2` | [O] | średnia |
| B13 | 9 połączeń wpust→odbiornik bez odcinka | 9 z 449 | [O] | niska |
| B14 | Arkusz łamie własną legendę | 2 wiersze | [P] | niska |

---

## 2. Metodyka

Sprawdzono trzy źródła **niezależnie od siebie**, żeby dało się odróżnić błąd odczytu od
błędu dokumentacji:

| Źródło | Co z niego wzięto |
|---|---|
| `data/baza-startowa/budowa.sqlite3` | 1059 obiektów, 649 odcinków, 7 439,5 m — stan po imporcie |
| `docs/Materiał.xlsx` | 4 arkusze czytane wprost (`zipfile` + `ElementTree`), z pominięciem importera |
| `docs/!!_DK29_osnowa_ok_v1.txt` | 151 punktów, plik tekstowy |

**Czego nie sprawdzono i dlaczego.** W tym środowisku nie ma `PyMuPDF` ani `openpyxl`
(`import fitz` → `ModuleNotFoundError`), więc `Profile Scalone.pdf` i
`Plany sytuacyjne Scalone.pdf` **nie były otwierane bezpośrednio** — ich zawartość ocenia się
przez to, co trafiło do bazy. Tam, gdzie to rozróżnienie ma znaczenie (§4), jest zaznaczone.

Progi branżowe użyte w kontrolach są zebrane na początku skryptu. **Żaden z nich nie występuje
w `app/`** — to samo w sobie jest ustaleniem, opisanym w §9.

---

## 3. Błędy branżowe — [P]

### 3.1 Spadek poniżej minimum — 39 odcinków

Reguła praktyczna `i_min = 1/DN` (DN200 → 5‰, DN400 → 2,5‰, DN600 → 1,67‰). Najgorsze:

```
D111-D112    DN400  L= 42,50 m   i = 0,00‰   (min 2,50‰)   ← spadek dokładnie zerowy
SEP4-D103    DN500  L=175,00 m   i = 0,11‰   (min 2,00‰)
D47-D48      DN400  L= 84,00 m   i = 0,12‰   (min 2,50‰)
D4-D5        DN600  L= 86,00 m   i = 0,47‰   (min 1,67‰)
D15-D171     DN600  L= 46,50 m   i = 0,65‰   (min 1,67‰)
```

**Zastrzeżenie metodyczne, które trzeba postawić wprost:** `i_min = 1/DN` to reguła
praktyczna, nie zapis normy. Kryterium normowe wg **PN-EN 752** to **prędkość
samooczyszczania** (zwykle 0,7–0,8 m/s przy przepływie obliczeniowym), a danych o przepływach
w tym zbiorze **nie ma w ogóle** — ani natężeń deszczu, ani powierzchni zlewni, ani
współczynników spływu. Bez nich nie da się orzec, czy odcinek jest wadliwy. Ta lista wskazuje
**gdzie zajrzeć do obliczeń hydraulicznych**, a nie co poprawić.

### 3.2 Odcinki praktycznie płaskie — 8

|Δh| < 5 mm, czyli poniżej dokładności zapisu rzędnych:

```
D28-O6        L=  3,00 m      O7-D37       L=  9,50 m
SEP1a-D87.2   L=  7,00 m      D110-SEP5    L=  2,62 m
D111-D112     L= 42,50 m      SEP6-O10     L= 14,00 m
KT6-KT7       L=  7,97 m      KT11-KT12    L= 64,18 m
```

Pięć z ośmiu to krótkie wstawki przy urządzeniach podczyszczających (osadnik, separator) —
tam zerowy spadek bywa celowy. **`D111–D112` (42,5 m) i `KT11–KT12` (64,2 m) celowe nie są**
i wymagają wyjaśnienia. `KT11–KT12` leży na kanale tłocznym, gdzie spadek dna i tak nie ma
znaczenia hydraulicznego — patrz §3.6.

### 3.3 Przykrycie poniżej strefy przemarzania — 55 węzłów

Liczone jako `rzędna terenu proj. − rzędna dna kanału − OD`, gdzie **OD to średnica
zewnętrzna** z katalogu (DN300 → OD315, DN600 → OD630).

```
węzłów z przykryciem < 1,00 m:          76 z 126
z tego poniżej strefy przemarzania 0,8 m:  55
```

```
D91    0,32 m   (teren 82,02, dno 81,30, DN400)
D17    0,41 m   (teren 47,50, dno 46,77, DN300/OD315)
D171   0,44 m   (teren 48,86, dno 47,79, DN600/OD630)
D81    0,44 m   (teren 53,64, dno 52,80, DN400)
O1a    0,45 m   (teren 44,49, dno 43,41, DN600/OD630)
```

**To nie jest artefakt odczytu.** Kontrola niezależna, wprost z `Materiał.xlsx` / `Studnie`
(`RTp − RD1 − D1`, z pominięciem bazy i parsera PDF), daje **117 węzłów poniżej 1,00 m** —
jeszcze więcej, bo arkusz ma rzędną przewodu wylotowego dla większej liczby węzłów niż PDF.
Zgodność na próbkach: `D17` → 0,43 m, `D7` → 0,45 m, `D81` → 0,44 m.

Krosno Odrzańskie leży w **strefie przemarzania 0,8 m** (PN-81/B-03020, strefa I).

**Dwa powody, dla których to może być poprawne** — i dlatego jest to [P], nie [O]:
1. `RTp` przy studni to rzędna terenu **projektowanego**, która w rowie lub na skarpie jest
   niższa niż na jezdni. Kanał biegnący w rowie ma nad sobą mniej gruntu z definicji.
2. Przykrycie liczone od `RTp` **nie uwzględnia konstrukcji nawierzchni**. Pod jezdnią
   właściwe pytanie brzmi „ile gruntu nad rurą poniżej spodu konstrukcji", a tej rzędnej
   w dokumentacji odwodnienia po prostu nie ma — jest w branży drogowej (§10).

Lista jest więc listą miejsc do sprawdzenia przy nałożeniu profili drogowych, a nie listą
wad. Przy 55 pozycjach warto to zrobić zanim brygada wejdzie w wykop.

### 3.4 Wyloty bez wyniesienia nad dno rowu — 41

Źródło: `Materiał.xlsx` / `Wyloty`, kolumny `Rz.d.` i `Rz. Dna rowu/zbiornika`.

| Wyniesienie dna wylotu nad dno rowu | Wylotów |
|---|---:|
| ujemne (wylot **poniżej** dna rowu) | **0** |
| 0,00 m (równo z dnem rowu) | **30** |
| 0,00–0,10 m | **11** |
| 0,10–0,20 m | 50 |
| 0,20–0,50 m | 103 |
| powyżej 0,50 m | 235 |

```
Wyl2   dno 42,90  rów 42,90   +0,00      Wyl7   dno 45,21  rów 45,21   +0,00
Wyl8   dno 46,89  rów 46,89   +0,00      Wyl5   dno 44,75  rów 44,70   +0,05
Wyl10  dno 46,70  rów 46,70   +0,00      Wyl6   dno 46,62  rów 46,56   +0,06
```

Wylot posadowiony dokładnie na dnie rowu zamula się i pracuje z cofką. **Żaden nie jest
ujemny** — to nie jest katastrofa, to lista do potwierdzenia u projektanta razem z rzędną
zwierciadła wody miarodajnej w rowie. Uwaga z arkusza: *„wylot do rowu melioracyjnego umocnić
narzutem kamiennym zgodnie z dokumentacją projektową oraz **decyzją wodnoprawną**"* — czyli
rzędne wylotów są objęte pozwoleniem wodnoprawnym i ich zmiana nie jest decyzją wykonawcy.

### 3.5 Rozstaw studni ponad typowy limit — 10 odcinków

Limity przyjęte: DN ≤ 300 → 50 m, DN 400–600 → 70 m, DN > 600 → 100 m.

```
D104-D105   175,00 m   (DN nieznane)      D38-D40      84,50 m   (DN nieznane)
D37-D38     108,50 m   DN400              D47-D48      84,00 m   DN400
D129-D131    87,00 m   DN400              D50-D51      84,00 m   (DN nieznane)
D4-D5        86,00 m   DN600              D57-D59      72,50 m   DN400
```

Na 81 odcinków studnia–studnia. **`D104–D105` = 175 m** to przypadek osobny: trzykrotność
limitu i jednocześnie odcinek bez średnicy. Możliwe, że między tymi studniami jest studnia
pośrednia, której rysunek nie podał — wtedy to [O], nie [P]. Rozstrzyga rysunek.

### 3.6 Kanał tłoczny traktowany jak grawitacyjny — [P] + [O]

Profile `KT1`…`KT15` mają w bazie `typ_odniesienia = OS_PRZEWODU` (rozpoznane poprawnie — to
rurociąg ciśnieniowy, gdzie odniesieniem jest **oś rury**, nie dno). Mimo to **wszystkie
14 odcinków ma zapisany `spadek_promile`**, z wartościami od 0‰ do 43,4‰.

W rurociągu ciśnieniowym spadek dna nie ma znaczenia hydraulicznego. `spadek_ciagu.py`
i niwelator potraktują te odcinki tak samo jak grawitacyjne — co daje wyniki bez sensu
fizycznego dla **679,74 m** trasy.

---

## 4. Błędy odczytu dokumentacji — [O]

### 4.1 Skala niedowykrycia

```
odcinków z rozjazdem spadku rysunek ↔ rzędne:   67
odcinków o spadku > 100‰:                        55
odcinków krótszych niż 1 m:                      28
odcinków z flagą 'podejrzany' w bazie:            5
```

**Pięć flag na ~150 przypadków wymagających uwagi.** Przyczyna jest w progach:
`walidacja.MIN_DLUGOSC_M = 0.05` (5 cm) przepuszcza każdy odcinek 0,10 m,
a `MAX_SPADEK_PROMILE = 200` przepuszcza wszystko poniżej 20 %.

### 4.2 Rzędna spoza profilu — `D97–D98`

```
D97-D98   L = 13,00 m   rzędne 40,95 → 68,93   ⇒ 2152‰   (28 m spadku na 13 m)
```

W bloku `surowe` tego odcinka (profil `Wyl50`) są **trzy sprzeczne długości**: profil ma
`dlugosc_calkowita_m = 118`, etykieta średnicy mówi `Ø500 L=168.0m`, a suma odległości
cząstkowych daje 77,5 m. Wartość 68,93 nie należy do tego profilu — pozostałe rzędne w nim
krążą wokół 40–41 m n.p.m. Parser sięgnął do sąsiedniego bloku.

Drugi taki przypadek: **`D115–D117.1`**, 44,78 → 50,67 na 10 m (589‰), profil `Wp17`.

### 4.3 Odcinki o nieodczytanym pikietażu — 28

Trzy o długości 0,00 m (oflagowane) i 25 poniżej 1 m (nieoflagowane). Pięć najgorszych:

```
Wyl220-Wp219   L=0,10 m   rysunek 150‰   rzędne 4500‰
Wyl221-Wp220   L=0,10 m   rysunek 150‰   rzędne 4500‰
Wyl116-Wp84    L=0,10 m   rysunek  90‰   rzędne 3400‰
Wyl218-Wp217   L=0,20 m   rysunek 150‰   rzędne 2400‰
Wyl219-Wp218   L=0,20 m   rysunek 150‰   rzędne 2350‰
```

Wzorzec jest jednoznaczny: rysunek podaje sensowny spadek (90–150‰ dla stromego przykanalika
od wpustu), rzędne też są sensowne, **zepsuta jest wyłącznie długość**. Pikietaż nie został
odczytany i spadł do wartości resztkowej.

### 4.4 Kanał tłoczny bez początku i bez końca — **ustalenie krytyczne**

Trzy powiązane usterki dają jeden skutek:

**(a) `KT15 = D139` — alias zadeklarowany, nie zastosowany.**
[`sonnet-think-output/02-analiza-profile-scalone.md`](sonnet-think-output/02-analiza-profile-scalone.md)
pisze: *„zapis równości: to jeden obiekt o dwóch oznaczeniach. Główny kod `KT15`, `D139`
zapisuję jako alias"*. W bazie są to **dwa osobne wiersze**:

```
KT15   id=305   WEZEL_KT   rz. dna 85,00   (opis pusty)
D139   id=255   STUDNIA    rz. dna 84,87   "Studnia rozprężna"
```

Model nie ma w ogóle kolumny na alias.

**(b) `K1` „Przepompownia wód opadowych, Rz.d.=79.04" nie istnieje w bazie**, choć jest
w arkuszu `Studnie`. Nie ma też typu `PRZEPOMPOWNIA` w modelu.

**(c) Skutek:** gałąź `KT1…KT15` jest **jedyną składową grafu bez wylotu** — 15 obiektów,
679,74 m, bez pompy na początku i bez studni rozprężnej na końcu. Woda w modelu nie ma skąd
przyjść ani dokąd odpłynąć.

### 4.5 Obiekty z arkusza nieobecne w bazie

```
K1     Przepompownia wód opadowych, Rz.d.=79.04
Sch1   Studnia chłonna
Sch2   Studnia chłonna
```

`Sch1`/`Sch2` to **urządzenia wodne w rozumieniu Prawa wodnego** (rozsączanie do gruntu),
a nie studnie rewizyjne — inny reżim formalny, inne badania odbiorowe, inne utrzymanie.
Model nie ma dla nich typu.

### 4.6 Dziewięć połączeń znanych arkuszowi, nieobecnych w rysunku

Arkusz `Wpusty` ma kolumnę `Odbiornik` — **autorytatywny graf 449 połączeń**. Dziewięć z nich
nie ma odpowiadającego odcinka w bazie:

```
Wp2 → D26        Wp177 → Wyl178    Wp213 → Wyl214
Wp5 → Wyl6.2     Wp199 → Wyl200    Wp230 → Wyl232
Wp170 → Wyl171   Wp208 → Wyl209    Wp247 → Wyl249
```

Osiem z dziewięciu to wpust → wylot. Importer tej kolumny **nie czyta wcale** — gdyby czytał,
te dziewięć braków samo by się uzupełniło, a pozostałe 440 stanowiłoby niezależną kontrolę
odczytu rysunku.

### 4.7 Sprostowanie: 399 składowych grafu to **nie** jest błąd

Sieć rozpada się na **399 składowych spójnych**, największa ma 15 obiektów. To wygląda
alarmująco i **nie jest usterką**:

```
składowych spójnych:                                    399
wylotów w sieci:                                        420
par wpust→odbiornik mieszczących się w jednej składowej: 441 z 449
```

Odwodnienie drogowe to wiele krótkich, niezależnych zlewni, każda z własnym wylotem do rowu.
Liczba składowych odpowiada liczbie wylotów, a graf z arkusza potwierdza spójność w 98 %
przypadków. Wyjątek jest **jeden** — kanał tłoczny z §4.4.

Zapisane tutaj, bo przy pobieżnym spojrzeniu ta liczba prowokuje do „naprawiania" czegoś,
co działa poprawnie.

---

## 5. Braki danych — [B]

### 5.1 Kompletność

| Pole | Wypełnione | |
|---|---:|---|
| odcinki: `dlugosc_m` | 648 / 649 | 99,8 % |
| odcinki: `dn_mm` | 446 / 649 | 68,7 % |
| odcinki: `spadek_promile` | 556 / 649 | 85,7 % |
| odcinki: **`material`** | **1 / 649** | **0,2 %** |
| odcinki: komplet (L + DN + i) | 412 / 649 | 63,5 % |
| obiekty: **`material`** | **0 / 1059** | **0 %** |
| obiekty: **`x`, `y`** | **0 / 1059** | **0 %** |

**Bez średnicy: 203 odcinki = 2 895,2 m, czyli 39 % długości sieci.** Dla tych odcinków nie
da się ani zamówić rury, ani policzyć przelicznika 3 m / 6 m.

### 5.2 Klasa SN jest w źródle i nie dociera do odcinka

To najbardziej odwracalny brak w całym zbiorze — **dane istnieją, importer ich nie czyta**:

```
Materiał.xlsx / Studnie, kolumna V:  SN8 ×171, SN10 ×6 (z zakresami: "SN10 od D32-D170"),
                                     PEHD ×1, brak ×5
Materiał.xlsx / Wpusty,  kolumna R:  "rura SN10" ×393, "rura SN12" ×56
```

W bazie: **0 obiektów i 1 odcinek z materiałem.** Klasa sztywności decyduje o tym, jaką rurę
wolno położyć w danym wykopie przy danym przykryciu i obciążeniu ruchem. Dziś brygadzista nie
ma jak tego sprawdzić w narzędziu, mimo że projektant to zapisał.

### 5.3 Pozostałe dane obecne w arkuszu, nieobecne w bazie

| Dane | Gdzie są | Po co |
|---|---|---|
| Kąty `K0`, `K1`, `K2` (zegary włączeń) | `Studnie`, kol. Q–S | montaż studni, orientacja kinet |
| Stan zegarów | `Studnie`, kol. X | „zegary potwierdzone" / „do potwierdzenia" / „wbudowana" |
| Odniesienia **KPED** | `Wyloty`, kol. H | `KPED 2.16`, `2.19`, `1.20` — typ konstrukcji wylotu |
| Rzędne włączeń `Dw1/Rw1`, `Dw2/Rw2` | `Studnie`, kol. M–P | rzędne wlotów bocznych |

### 5.4 Kanał tłoczny bez opisu materiałowego

```
odcinków KT: 14, długość 679,74 m, bez DN: 13, bez materiału: 13
```

Cała trasa to **PE100 SDR17 DN250** — wiadomo to z arkusza `RURY` (pozycja „Rura PE 100
SDR 17 250X14,8 prosta odcinki ZINPLAST", 680 m, co zgadza się z 679,74 m z profili co do
0,3 m). W bazie tylko **1 z 14** odcinków ma tę informację.

---

## 6. Zestawienie materiałowe — [O]

### 6.1 Podwójne liczenie zapotrzebowania

```
suma kolumny ilosc_projekt_m w bazie:        11 020,8 m
z tego pozycje rurowe:                       10 299,8 m
po odjęciu duplikatu wariantu /3 i /6:        5 149,9 m
długość sieci wg profili:                     7 439,5 m
```

Arkusz `RURY` podaje **tę samą ilość projektową dwa razy** — raz dla rur 3 m, raz dla 6 m,
bo to dwa warianty handlowe jednego zapotrzebowania. Dziewięć par ma identyczną wartość:

```
OD200 SN10   /3 → 2155      /6 → 2155
OD400 SN8    /3 → 1310,5    /6 → 1310,5
OD500 SN8    /3 →  581,4    /6 →  581,4
OD630 SN8    /3 →  278,1    /6 →  278,1        (+ 5 dalszych)
```

**Każde zestawienie sumujące tę kolumnę jest podwojone.**

### 6.2 Kolumny J/K to osobny blok, wlany do tej samej listy

Arkusz `RURY` ma dwa niezależne bloki: **B–H** (opis, ilość projektowa, długość sztuki, ilość
zamówiona, dostawa, data, WZ) oraz **J–K** z własnymi nagłówkami **„Aneks nr 1"** i
**„Zamówienie nr 9125"**. Importer wlał oba do jednej listy, a ilości z kolumny K trafiły
do pola `ilosc_projekt_m`.

Skutek: pozycje 21–32 (rura PE, trójniki, kolana, uszczelki, łuki) mają „ilość projektową"
wziętą z aneksu do zamówienia. To **dwie różne wielkości pod jedną nazwą**.

### 6.3 Wiersz nagłówkowy jako pozycja materiałowa

```
material_item id=1   "STUDNIE DN1200"   wszystkie ilości NULL
```

To komórka `B4` — nagłówek grupy kolumn. Sąsiednia `C4` zawiera literówkę „STUDNIE **ND**1500".

### 6.4 Trzynaście pozycji bez rozpoznanej średnicy

Parser czyta średnicę wyłącznie ze wzorca `Rura kanal. SN X NNN/L`. Poza nim zostaje:

```
id 21  Rura PE 100 SDR 17 250X14,8 ... ZINPLAST        680 m   ← cały kanał tłoczny
id 22  Trójnik redukcyjny OD 200/200/160 SN 8            6
id 24  KOLANO PRAGMA OD 90 st DN250 SN 8                 5
id 30  Łuk PE 100 SDR 17 DN 250 kąt 90 st                2      (+ 9 dalszych)
```

`rury.PROFIL_NA_OD` nie zna PE100 SDR17, więc **680 m kanału tłocznego nie da się przeliczyć
na rury ani rozliczyć** — mimo że materiał jest zamówiony i częściowo dostarczony.

### 6.5 Długości wg średnicy: profile kontra arkusz

| DN | OD | PDF [m] | XLSX [m] | różnica |
|---:|---:|---:|---:|---:|
| 200 | 200 | 2 157,4 | 2 443,3 | +285,9 |
| 250 | 250 | 206,4 | 213,1 | +6,7 |
| 300 | 315 | 103,0 | 126,0 | +23,0 |
| 400 | 400 | 1 205,0 | 1 458,8 | +253,8 |
| 500 | 500 | 554,5 | 677,6 | +123,1 |
| **600** | **630** | **302,0** | **278,1** | **−23,9** ← niedobór |
| 1000 | 1000 | 16,0 | 16,0 | 0,0 |

Nadwyżki są normalne — to zapas na docinki. **DN600/OD630 jest jedynym niedoborem** i warto
go sprawdzić, zanim brygada wejdzie na te odcinki.

**Zastrzeżenie:** 203 odcinki (2 895,2 m) nie mają średnicy, więc kolumna „PDF" jest **dolnym
oszacowaniem** dla pozostałych średnic. Przy DN600 dolne oszacowanie już przekracza zamówienie
— dlatego akurat ten wiersz jest wiarygodny, a pozostałe nadwyżki mogą być pozorne.

### 6.6 Arkusz łamie własną legendę — [P]

Legenda arkusza `Studnie` mówi `Gł = Rz.g. − Rz.d.`. Dwa wiersze tego nie spełniają:

```
Sch1   Rz.g 88,03 − Rz.d 84,71 = 3,32,  a Gł podane 2,50
Sch2   Rz.g 88,65 − Rz.d 85,04 = 3,61,  a Gł podane 2,50
```

Oba to studnie chłonne — te same, których nie ma w bazie (§4.5). Prawdopodobnie „Gł" oznacza
tu głębokość **części chłonnej**, a nie całej studni, ale legenda tego nie przewiduje.

---

## 7. Osnowa i „mapa z reperami"

### 7.1 Ryzyko nr 1: układ wysokościowy niezadeklarowany — [B]

`!!_DK29_osnowa_ok_v1.txt` to 151 wierszy w formacie `nazwa,X,Y,H`, **bez nagłówka i bez
jednego bajtu metadanych**:

```
o1,5771146.485,5503774.889,44.54730
```

Brak: **układu wysokościowego**, klasy i dokładności punktu, rodzaju stabilizacji, daty
pomiaru, opisu topograficznego, numeru operatu.

**Dlaczego to jest ryzyko nr 1:** różnica między **Kronsztadt'86** a **PL-EVRF2007-NH**
wynosi w Polsce średnio **0,1649 m**, a Kronsztadt'86 przestał obowiązywać w pomiarach
geodezyjnych **1 stycznia 2024**. Jeżeli osnowa jest w starym układzie, a geodeta nawiąże się
do repera PODGiK w nowym (albo odwrotnie), cała sieć dostanie **systematyczne przesunięcie
16,5 cm**.

Skala porównawcza: przykanalik DN200 o długości 17 m przy spadku 5‰ ma **cały spadek
projektowy równy 0,085 m** — połowę tego błędu. Na odcinkach z §3.1 (0,11‰ na 175 m → 0,02 m)
błąd jest **ośmiokrotnie większy niż cały projektowy spadek odcinka**.

**Do ustalenia przed pierwszym tyczeniem, nie po.**

### 7.2 Kompletność osnowy

```
punktów w pliku:                  151
numeracja:                        o1 … o1562  →  1412 luk
odstęp między kolejnymi punktami: min 15,3 m, mediana 137,7 m, max 363,4 m
wysokości zapisane z:             5 miejscami po przecinku (0,01 mm)
```

- **1412 luk w numeracji.** Nic nie mówi, czy to wybór punktów dla tego odcinka, czy punkty
  zniszczone. Dla wykonawcy to różnica między „szukaj dalej" a „nie ma czego szukać".
- **Maksymalny odstęp 363,4 m.** Przy niwelacji technicznej to ciąg, którego nie ma czym
  domknąć bez punktu pośredniego.
- **Wysokości z dokładnością 0,01 mm** przy nieznanym błędzie punktu to dokładność pozorna —
  sugeruje precyzję, której zapis nie potwierdza.

### 7.3 Wszystkie punkty zaimportowane jako `REPER` — [O]

```
w bazie: typ {'REPER': 151}, układ {'PL-2000/5': 151}
```

Każdy punkt ma komplet X, Y, H — to **osnowa realizacyjna** (poziomo-wysokościowa), a nie
repery niwelacyjne. Rozróżnienie nie jest formalnością: decyduje o tym, co wolno z punktu
wyznaczać i z jaką dokładnością. Układ **poziomy** (`PL-2000/5`) jest zapisany poprawnie —
brakuje wyłącznie **wysokościowego**.

### 7.4 Mapy z reperami faktycznie nie ma — [B]

```
network_object.x, .y     0 z 1059
plan_location            0 wierszy
plan_georef              0 wierszy
plan_anchor              0 wierszy
pomiar_wykonawczy        0 wierszy
```

Mechanizm jest napisany i opisany — przekształcenie Helmerta w `georef.py`, wektoryzacja sieci
po stylu kreski w `plan_wektor.py`, eksport do GeoJSON/DXF/CSV w `plan_eksport.py` — ale
**nigdy nie uruchomiony na danych**. Dopóki tak jest:

- żaden obiekt nie ma współrzędnych, więc nie da się go wytyczyć z odbiornika GNSS,
- „najbliższe repery" nie mają jak zadziałać (to samo zastrzeżenie co w `11-audyt-danych.md`, A7),
- nie ma podstawy do geodezyjnej inwentaryzacji powykonawczej ani do zgłoszenia do GESUT.

To jedyna pozycja w tym raporcie, która **nie wymaga żadnej decyzji projektanta** — wystarczy
wskazać dwie kotwice na arkuszu i uruchomić to, co już jest.

---

## 8. Dlaczego narzędzie tego nie wyłapało

Nie jako lista zadań — jako przyczyna źródłowa. Ustalone przeglądem kodu.

**Walidator nie zna ani jednej normy branżowej.** `app/services/walidacja.py` ma dokładnie
dwa progi liczbowe: `MAX_SPADEK_PROMILE = 200` i `MAX_DLUGOSC_M = 300`, oba opisane w kodzie
jako granice zdrowego rozsądku. Brak spadku minimalnego, przykrycia, rozstawu studni, kontroli
przeciwspadku, wyniesienia wylotu. Próg 300 m nie wyłapie odcinka bez studni pośredniej, bo
typowy rozstaw to 50–70 m.

**Flaga `podejrzany` niczego nie blokuje.** Komentarz w `walidacja.py:140` zapowiada
„kategorie, które dyskwalifikują odcinek do liczenia rur i tyczenia", ale w `rury.py`,
`materialy.py` i `blueprints/api.py` nie ma do niej **ani jednego odwołania**. Flaga jest
wyłącznie prezentacyjna — czerwona ramka na karcie odcinka.

**Cztery różne progi na tę samą wielkość.** Rozjazd spadku jest sygnalizowany przy
`> 1‰` (`pages/odcinki.html`), `> 5‰` (`partials/karta_odcinka.html`), `max(5‰, 15 %)`
(`walidacja.py:105`) i `max(1‰, 15 %)` (`pdf_profile_parser.py:647`). Cztery różne odpowiedzi
na to samo pytanie, zależnie od tego, gdzie użytkownik spojrzy.

**Dwie niezgodne definicje długości odcinka.** `rury.py` liczy oś–oś (zamówienie materiału),
`spadek_ciagu.py` ściana–ściana po odjęciu promieni studni (tyczenie). Obie decyzje są
uzasadnione w swoich docstringach, ale **nigdzie się nie spotykają** — nie ma miejsca, które
by tę różnicę uzgadniało albo choćby raportowało.

**Przeciwspadek jest niewidoczny w całym łańcuchu.** `abs()` w `importer.py:296`,
`network.py:348` i `spadek_ciagu.py:164` sprawia, że odcinek płynący pod górę wygląda
identycznie jak poprawny. Kierunek istnieje jako opisowe `kierunek_rysunku`, ale nic go nie
sprawdza.

**`leveling.przykrycie()` używa DN zamiast OD** — zawyża o 15 mm dla DN300 i 30 mm dla DN600,
rozjeżdżając się z `rury.PROFIL_NA_OD` w tym samym projekcie. Funkcja niczego nie ocenia,
tylko wyświetla liczbę.

**`NIEZMIENNIK_RZEDNYCH` jest po imporcie PDF martwy** — `importer._uzgodnij_zaglebienia`
naprawia dane, zanim reguła zdąży je sprawdzić.

**`CiagNiwelacyjny.f_dop`** liczy `0.020 × √max(L_km, 0.0001)`, więc przy niepodanej długości
odchyłka dopuszczalna spada do 0,2 mm i `czy_ok()` zwraca `False` zamiast „nie wiem".

---

## 9. Jak powinno być — standardy PL i UE

### 9.1 Plany i profile

**Stan dziś.** Rysunki są generowane maszynowo („Profil Koordynator 8.0"), wektorowe,
z czytelną strukturą pasm — to akurat mocna strona tego zbioru. Problem jest w tym, że
**rysunek jest jedynym nośnikiem geometrii**: długości, średnice i spadki istnieją wyłącznie
jako napisy na papierze, więc każdy odczyt jest rekonstrukcją.

**Ramy prawne i normowe:**

- **[Rozporządzenie Ministra Infrastruktury z 24.06.2022 w sprawie przepisów
  techniczno-budowlanych dotyczących dróg publicznych](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20220001518)**
  (Dz.U. 2022 poz. 1518, obowiązuje od **21.09.2022**) — zastąpiło przepisy sprzed ponad
  20 lat. To akt **powszechnie obowiązujący**.
- **[WR-D-71 „Wytyczne projektowania urządzeń do odwodnienia dróg zamiejskich i ulic"](https://www.gov.pl/attachment/b4b35d7a-8980-4634-8bea-22be7bf8efe3)** —
  cz. 1 „Wymagania podstawowe" (rekomendacja MI 28.11.2023), cz. 2 „Odwodnienie powierzchniowe
  i wgłębne" (5.12.2023). **Status: standard rekomendowany, stosowanie dobrowolne** zgodnie
  z ustawą o drogach publicznych — nie są to przepisy techniczno-budowlane. Warto to wiedzieć,
  zanim ktoś powoła się na WR-D jak na normę obowiązującą.
- **WR-D-22** — wytyczne projektowania dróg zamiejskich (kształtowanie geometryczne,
  wyposażenie techniczne).
- **PN-EN 752** — projektowanie i eksploatacja systemów kanalizacyjnych (kryterium
  samooczyszczania zamiast sztywnego `i_min`).
- **PN-EN 1610** — wykonanie i badania przewodów: próba szczelności powietrzem lub wodą,
  posadowienie, zasypka. To ta norma rządzi odbiorem.
- **PN-EN 13476** (rury PP o ściance strukturalnej — czyli PRAGMA z tego projektu),
  **PN-EN 1917** / **PN-EN 13598** (studzienki betonowe / z tworzyw).

**Co zmienić konkretnie.** Dostarczać razem z PDF **plik wymiany** (§9.4), w którym
długość, średnica, klasa SN i rzędne są danymi, nie napisami. Rysunek zostaje jako dokument
formalny; narzędzia czytają plik.

### 9.2 Baza materiałów

**Stan dziś.** Jedna kolumna `ilosc_projekt_m` niesie **cztery różne wielkości** naraz:
zapotrzebowanie projektowe, wariant handlowy, pozycję z aneksu i pozycję z zamówienia.
Dlatego się sumuje podwójnie (§6.1) i dlatego 680 m rury PE ma „ilość projektową" z aneksu
(§6.2).

**Jak powinno być — cztery osobne byty:**

| Byt | Klucz | Przykład |
|---|---|---|
| **Zapotrzebowanie projektowe** | DN + klasa SN + materiał | OD200 SN10 PP — 2 155 m |
| **Wariant handlowy** | odcinek 3 m / 6 m | jak rozbić te 2 155 m |
| **Zamówienie / aneks** | numer + data | „Aneks nr 1", „Zamówienie 9125" |
| **Dostawa** | numer WZ + data | WZ 524152812, 711 m |

Klucz pozycji to **DN + SN + materiał**, nigdy tekst opisu — dziś `dn_od_mm` jest NULL dla
13 pozycji tylko dlatego, że opis nie pasował do wzorca (§6.4).

Do tego **powiązanie pozycji z odcinkiem**. Dopóki klasa SN nie dociera do odcinka (§5.2),
zestawienie materiałowe i sieć są dwoma niezależnymi zbiorami, których nikt nie uzgadnia.

### 9.3 Osnowa i mapa reperów

**Stan dziś.** Cztery kolumny bez metadanych, wszystko jako `REPER`, brak układu
wysokościowego, zero georeferencji obiektów.

**Jak powinno być:**

- Układ poziomy **PL-2000 strefa 5** — jest, zapisany poprawnie.
- Układ wysokościowy **[PL-EVRF2007-NH](https://pl.wikipedia.org/wiki/PL-EVRF2007-NH)**
  zadeklarowany **jawnie w pliku**. Kronsztadt'86 przestał obowiązywać 1.01.2024; różnica
  0,1649 m. Jeżeli dane są w starym układzie — udokumentować to i przeliczyć świadomie,
  a nie domyślnie.
- Dla każdego punktu: klasa/dokładność, rodzaj stabilizacji, data pomiaru, opis topograficzny,
  numer operatu. Bez opisu topograficznego punktu w terenie się nie odnajdzie.
- **Geodezyjna inwentaryzacja powykonawcza** → zgłoszenie do **GESUT**. To i tak będzie
  wymagane przy odbiorze — lepiej zbierać X, Y, H na bieżąco niż odtwarzać po zasypaniu wykopu.
- Docelowo: każdy obiekt sieci z X, Y w PL-2000/5 i H w PL-EVRF2007-NH. W tym projekcie
  wystarczy uruchomić `georef.py`, który już istnieje (§7.4).

### 9.4 Wymiana danych — poziom UE

Tu leży odpowiedź na pytanie „dlaczego w ogóle musimy czytać dane z rysunku".

- **ISO 19650-1/2** (w Polsce **PN-EN ISO 19650**) — zarządzanie informacją w cyklu życia
  obiektu, wspólne środowisko danych (CDE). Definiuje, kto wydaje jaką wersję i jak się ją
  oznacza — czyli dokładnie to, czego brakuje przy 41 rozbieżnościach PDF ↔ XLSX, gdzie nie
  wiadomo, które źródło jest aktualne.
- **IFC 4.3 / ISO 16739** — format otwarty, od wersji 4.3 obsługuje infrastrukturę liniową
  (drogi, sieci). Model, w którym rura ma DN, SN, materiał i rzędne jako **atrybuty**.
- **LandXML** — niweleta, przekroje, punkty osnowy; najprostsza droga do wymiany danych
  drogowych, jeśli pełny BIM jest poza zasięgiem.
- **INSPIRE** (dyrektywa 2007/2/WE), temat *Utility and governmental services* — warstwa sieci
  uzbrojenia terenu.
- **Dyrektywa 2014/24/UE, art. 22 ust. 4** — podstawa, na której zamawiający publiczni mogą
  wymagać BIM w zamówieniach.

**Sedno praktyczne:** komplet `DN + SN + materiał + rzędne + X,Y` w jednym wymienialnym
modelu to dokładnie zbiór, którego brak generuje **większość ustaleń tego raportu** —
B4, B5, B9, B11 i połowę B7. To nie jest postulat na przyszłość, tylko diagnoza teraźniejszości.

---

## 10. Nałożenie branży drogowej — odpowiedź na pytanie

**Tak, da się** — i sporą część mechanizmu to repozytorium już ma:

| Element | Gdzie | Co robi |
|---|---|---|
| Wycięcie sieci z planu | `app/services/plan_wektor.py` | po stylu kreski z legendy, bez OCR |
| Związanie arkusza z terenem | `app/services/georef.py` | przekształcenie Helmerta → PL-2000/5 |
| Odczyt profili | `app/services/pdf_profile_parser.py` | po współrzędnych, z rozróżnieniem pasm |
| Eksport | `app/services/plan_eksport.py` | GeoJSON / DXF / CSV |

Nałożenie sprowadza się do **wspólnego układu odniesienia**: gdy oba komplety rysunków są
związane z PL-2000/5, reszta jest arytmetyką.

### Co jest potrzebne, w kolejności od najlepszego

1. **DWG/DXF lub LandXML** — niweleta, przekroje normalne i konstrukcja nawierzchni wchodzą
   wprost, bez zgadywania skali. Przypadek idealny.
2. **Wektorowy PDF** (jak `Profile Scalone.pdf`) — działa, tą samą metodą co dotychczas.
   Wymaga środowiska z PyMuPDF.
3. **Skan lub raster** — konieczna georeferencja po punktach; wynik przybliżony, nadaje się
   do wskazywania miejsc, nie do liczenia rzędnych.

Przy każdym wariancie potrzebna jest **kotwica**: dwa punkty o znanych X, Y wspólne dla obu
branż (najlepiej z osnowy), oraz **deklaracja układu wysokościowego** — bo bez niej nakładanie
profili jest nakładaniem dwóch układów o nieznanym wzajemnym przesunięciu (§7.1).

### Co wyjdzie z nałożenia, a dziś jest niesprawdzalne

- **Przykrycie liczone od spodu konstrukcji nawierzchni**, a nie od `RTp`. To rozstrzygnie
  §3.3 w jedną albo w drugą stronę — 55 węzłów albo się wyjaśni, albo okaże poważniejszym
  problemem, niż wygląda.
- **Zgodność `RTp` z niweletą drogi.** Dziś rzędna terenu projektowanego w profilu kanalizacji
  jest przyjmowana na wiarę; przy 41 rozbieżnościach PDF ↔ XLSX (w tym `Wp428` z różnicą 7 m)
  niweleta drogi jest rozjemcą.
- **Położenie wpustów względem krawężnika i ścieku** — czy wpust faktycznie stoi tam, gdzie
  spływa woda.
- **Rzędne dna rowu przy 41 wylotach z §3.4** — profil rowu z branży drogowej powie, czy
  wyniesienie 0,00 m jest błędem, czy świadomym rozwiązaniem.
- **Kolizje z pozostałymi branżami** — teletechnika, energetyka, wodociąg.

### Ograniczenie, o którym trzeba wiedzieć z góry

W środowisku, w którym powstał ten raport, **nie ma PyMuPDF ani openpyxl**. Wszystkie liczby
policzono na SQLite i na `Materiał.xlsx` rozpakowanym `zipfile` + `ElementTree`. Analiza
plików drogowych będzie wymagała środowiska z PyMuPDF — czyli **Dockera, nie Termuxa**
(por. [`project-docs/16-termux.md`](project-docs/16-termux.md)).

---

## 11. Co zrobić najpierw

Kolejność wg stosunku ryzyka do kosztu, nie wg numeracji ustaleń.

1. **Ustalić układ wysokościowy osnowy** (B1) — jedno pytanie do geodety. Blokuje wiarygodność
   każdej rzędnej w projekcie. Zero kosztu, największa waga.
2. **Uruchomić georeferencję** (B9) — mechanizm gotowy, trzeba wskazać dwie kotwice.
   Odblokowuje współrzędne, repery i podstawę do inwentaryzacji powykonawczej.
3. **Wczytać klasę SN i kolumnę `Odbiornik`** z arkusza (B5, B13) — dane są, importer ich
   nie czyta. Domyka też 9 brakujących połączeń i daje niezależną kontrolę odczytu rysunku.
4. **Naprawić kanał tłoczny** (B2) — alias `KT15 = D139`, obiekt `K1`, typ `PRZEPOMPOWNIA`,
   PE100 SDR17 w katalogu rur. 680 m trasy jest dziś poza narzędziem.
5. **Rozdzielić kolumny zestawienia materiałowego** (B4) — dopóki zapotrzebowanie i zamówienie
   siedzą w jednym polu, żadne podsumowanie nie jest wiarygodne.
6. **Przekazać projektantowi listy [P]** — §3.1 (39 odcinków), §3.3 (55 węzłów), §3.4
   (41 wylotów), §3.5 (10 rozstawów). Z pytaniem, nie z tezą.

---

## Powiązane

- [`project-docs/11-audyt-danych.md`](project-docs/11-audyt-danych.md) — audyt przepływu danych
- [`sonnet-think-output/02-analiza-profile-scalone.md`](sonnet-think-output/02-analiza-profile-scalone.md) — jak czytany jest rysunek
- [`sonnet-think-output/01-niwelacja-podstawy.md`](sonnet-think-output/01-niwelacja-podstawy.md) — reper, rzędne, wzory
- [`project-docs/10-georeferencja.md`](project-docs/10-georeferencja.md) — związanie arkusza z terenem
- [`scripts/audyt_branzowy.py`](../scripts/audyt_branzowy.py) — dowód liczbowy do tego raportu
