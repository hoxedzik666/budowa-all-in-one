# Niwelacja w robotach wod-kan — co znalazłem i jak to rozumiem

> Notatka robocza do modułu `app/services/leveling.py`. Spisuję to, co musiałem
> zrozumieć, żeby napisać kalkulator, który nie kłamie brygadziście przy wykopie.

---

## 1. Rzędna — punkt wyjścia do wszystkiego

**Rzędna** to wysokość punktu nad przyjętym poziomem odniesienia, podawana w
**metrach nad poziomem morza (m n.p.m.)**. W dokumentacji tego projektu wszystkie
liczby przy profilach to rzędne — od 39 do 90 m n.p.m.

W Polsce funkcjonują dwa układy wysokościowe i to **nie jest** szczegół
formalny — różnica między nimi to kilkanaście centymetrów:

| Układ | Opis | Uwaga |
|---|---|---|
| **PL-KRON86-NH** | Kronsztadt'86, poziom Morza Bałtyckiego w Kronsztadzie | układ historyczny, wciąż w wielu operatach |
| **PL-EVRF2007-NH** | europejski, obowiązujący układ państwowy | wartości wyższe o ok. 14–20 cm zależnie od rejonu |

⚠️ **Czego nie wiem:** plik `!!_DK29_osnowa_ok_v1.txt` podaje same liczby
(`nazwa,X,Y,H`) bez nagłówka i bez informacji o układzie. Wysokości repera
zapisałem tak, jak są. **Przed pierwszym tyczeniem trzeba sprawdzić w operacie
geodezyjnym, w jakim układzie jest osnowa** — pomyłka daje systematyczny błąd
~15 cm na całej budowie.

Współrzędne poziome rozpoznałem jako **PL-2000 strefa 5** (południk osiowy 15°E):
X ≈ 5 764 000–5 771 000 (północ), Y ≈ 5 503 000–5 510 000 (wschód).

---

## 2. Reper

**Reper** to trwale zastabilizowany punkt o **znanej, pomierzonej rzędnej**.
To fizyczna kotwica całego pomiaru wysokościowego — wszystko, co mierzysz
niwelatorem, jest liczone *względem repera*.

Rodzaje, na które trafiłem:

- **Reper państwowy** (osnowa podstawowa/szczegółowa) — bolec, znak ścienny albo
  słup, wpisany do państwowego zasobu geodezyjnego. Rzędna z operatu.
- **Reper roboczy** — założony na potrzeby budowy, nawiązany do repera
  państwowego. Zwykle bolec w betonowym fundamencie, w trwałym elemencie
  (przepust, fundament, cokół) — koniecznie **poza strefą robót ziemnych**,
  żeby koparka go nie ruszyła.

Plik `!!_DK29_osnowa_ok_v1.txt` zawiera **151 punktów** o nazwach `o1`…`o180`
(z lukami). Traktuję je jako **osnowę roboczą / repery** dla tej budowy.

**Praktyka:** reper trzeba okresowo kontrolować. Jeżeli między pomiarami wynik
„ucieka" o kilka centymetrów w jednym kierunku, prawdopodobnie ruszył się reper
albo instrument — nie grunt.

---

## 3. Rzędna projektowa vs rzędna terenu

Na profilu podłużnym z tego projektu występują **cztery** rzędne dla każdego
węzła. To rozróżnienie jest kluczowe:

| Nazwa na rysunku | Co to jest |
|---|---|
| **RZĘDNA TERENU ISTN.** | teren *przed* robotami — jak jest dzisiaj |
| **RZĘDNA TERENU PROJ.** | teren *po* robotach — docelowa niweleta drogi/terenu |
| **RZĘDNA DNA KANAŁU** | wewnętrzny spód rury; to do niej odnosi się spadek |
| **ZAGŁĘBIENIE DNA KANAŁU** | ile metrów dna kanału jest pod terenem projektowanym |

**Rzędna projektowa** to ogólnie każda zaprojektowana wysokość. W kontekście
wod-kan „rzędna projektowa" najczęściej znaczy **rzędna dna kanału** — bo to
ją się wytycza w wykopie.

### Zależność, którą zweryfikowałem na danych

```
zagłębienie = rzędna terenu projektowanego − rzędna dna kanału
```

Sprawdziłem to na **ponad 900 węzłach** z całego pliku — trzyma się z dokładnością
do 1 cm w ponad 99% przypadków. Używam jej jako walidatora importu (i do
rozstrzygania, która liczba należy do którego węzła, gdy studnia ma kilka wlotów).

**Zagłębienie ujemne jest poprawne.** Przykład z dokumentacji — `Wyl104`:
teren projektowany 83.60, dno kanału 84.00, zagłębienie **−0.40 m**. To wylot
wystający ze skarpy nad teren. Import nie może takich odrzucać.

---

## 4. Rzędna dna kanału a rzędna dna studni — to NIE to samo

To najczęstsze źródło pomyłek i najważniejsze rozróżnienie, jakie wyciągnąłem
z tego pliku.

W opisie obiektu na rysunku widnieje np.:

```
Studnia z piaskownikiem DN1500, Rz.d.=82.26
```

Ale w paśmie „RZĘDNA DNA KANAŁU" ten sam węzeł (`D155`) ma **82.76**.

- **82.76 m** — rzędna **dna kanału**: spód rury wchodzącej do studni.
- **82.26 m** — rzędna **dna studni** (`Rz.d.`): dno osadnika/piaskownika,
  **0.50 m niżej**.

To jest ta liczba, do której faktycznie kopie się wykop. Dla **osadnika**
różnica bywa **1.50 m**.

```
        teren projektowany  83.81  ──────────────
                                        │  1.05 m  = zagłębienie
        dno kanału          82.76  ─────┴────
                                        │  0.50 m  = piaskownik
        dno studni (Rz.d.)  82.26  ─────┴────   ← tu kończy koparka

        głębokość wykopu = 83.81 − 82.26 = 1.55 m
```

W bazie trzymam obie liczby w osobnych kolumnach
(`rzedna_dna_kanalu`, `rzedna_dna_studni`) i liczę z nich `glebokosc_wykopu`.

**Uwaga o studniach z wieloma rurami:** studnia ma tyle rzędnych dna, ile
wchodzi do niej rur na różnych wysokościach. Jako kanoniczną przyjmuję
**najniższą** (rzędna odpływu); pozostałe zapisuję jako włączenia.

---

## 5. Przykrycie i strefa przemarzania

**Przykrycie** liczy się od **wierzchu rury** do terenu — nie od dna:

```
przykrycie = rzędna terenu − (rzędna dna + średnica)
```

Dla `D155`: 83.81 − (82.76 + 0.50) = **0.55 m**.

Głębokość przemarzania gruntu wg **PN-81/B-03020** dzieli Polskę na cztery
strefy: **0.8 / 1.0 / 1.2 / 1.4 m**. Województwo lubuskie (Krosno Odrzańskie)
leży w strefie o najmniejszej głębokości przemarzania.

⚠️ Kanalizacja deszczowa działa okresowo, więc bywa układana płycej niż
wodociąg — a w miejscach z małym przykryciem stosuje się rury o wyższej
sztywności obwodowej (w dokumentacji widać `SN8`, `SN10`, `SN12`) albo
ocieplenie. **To decyzja projektanta, nie regułka** — moduł tylko pokazuje
wyliczone przykrycie, nie ocenia go.

---

## 6. Spadek

**Spadek** to stosunek różnicy rzędnych do długości odcinka:

```
i = (rzędna_dna_początek − rzędna_dna_koniec) / długość
```

Podaje się go w **procentach (%)** albo **promilach (‰)**; 1% = 10‰.
W tej dokumentacji rysunek podaje **procenty** (`0.3%`, `9%`, `0.5%`).
W bazie trzymam **promile** — to jednostka, w której zwykle mówi się o
kanalizacji grawitacyjnej, a procenty liczę z niej.

Przykład wzorcowy — odcinek `Wyl101–D155`:
```
długość 20.5 m, spadek 0.3% = 3‰
różnica rzędnych = 20.5 × 0.003 = 0.0615 m ≈ 0.06 m
82.76 − 82.70 = 0.06  ✓
```

**Zasada minimalnego spadku:** dla kanalizacji grawitacyjnej przyjmuje się
`i_min ≈ 1/DN` (DN w mm), czyli DN200 → ok. 5‰, DN300 → ok. 3.3‰. Chodzi o
utrzymanie prędkości samooczyszczania (ok. 0.7–0.8 m/s). Górna granica wynika
z prędkości maksymalnej (ok. 3–5 m/s), przy której ścierają się rury.

**Rzędna w dowolnym punkcie odcinka** — potrzebna, gdy tyczy się dno między
studniami:
```
rzędna(x) = rzędna_początkowa − spadek[‰] / 1000 × x[m]
```

### Uwaga o kierunku rysunku

Profile w tym pliku są rysowane **od wylotu w górę zlewni** — dno kanału *rośnie*
wzdłuż rysunku, mimo że woda płynie w drugą stronę. Dlatego spadek z rysunku
i spadek policzony z rzędnych mają przeciwne znaki. Porównuję je co do wartości
bezwzględnej, a kierunek zapisuję osobno (`surowe.kierunek_rysunku`).

---

## 7. Niwelator

### Budowa i rodzaje

**Niwelator** to instrument dający **poziomą oś celowej**. Elementy:

- **luneta** z krzyżem kresek (kreska pozioma = oś celowej, kreski dalmiercze
  do pomiaru odległości),
- **libella pudełkowa** do wstępnego poziomowania,
- **kompensator** — w **niwelatorze samopoziomującym** (dziś standard)
  automatycznie ustawia oś celowej poziomo po zgrubnym wypoziomowaniu,
- **śruby ustawcze** (trzy) i śruba leniwa do obrotu.

Rodzaje:

| Typ | Dokładność (błąd średni na 1 km podwójnej niwelacji) | Zastosowanie |
|---|---|---|
| techniczny (budowlany) | ok. 2–5 mm | roboty ziemne, wod-kan, tyczenie |
| precyzyjny | ok. 0.7–1.5 mm | osnowa, monitoring, konstrukcje |
| **kodowy (cyfrowy)** | 0.3–1.5 mm | odczyt automatyczny z łaty kodowej |

**Łata niwelacyjna** — najczęściej **4 m** (składana lub teleskopowa),
z podziałem centymetrowym (odczyt do 1 mm z interpolacji). Do precyzyjnych —
łata inwarowa. Łata musi stać **pionowo** (libella okrągła na łacie) i na
twardym punkcie — na dnie wykopu używa się **żabki/podstawki**, bo w błocie
łata się zapada.

### Niwelacja geometryczna „ze środka"

Instrument stawia się **w przybliżeniu w połowie** między łatami. Ten jeden
nawyk eliminuje naraz:
- błąd kolimacji (nierównoległość osi celowej i osi libelli),
- wpływ krzywizny Ziemi,
- w dużej mierze refrakcję.

Warto też pilnować, żeby celowa nie biegła zbyt nisko nad rozgrzanym gruntem —
drgania powietrza psują odczyt.

### Sprawdzenie instrumentu

Przed sezonem (i po każdym mocniejszym uderzeniu) — **próba dwóch stanowisk**:
mierzy się przewyższenie między dwoma punktami raz ze środka, raz z bliska
jednej łaty. Różnica wyników to błąd kolimacji. Jest to sprawdzian, który
robi się w 15 minut, a chroni przed systematycznym błędem na całej budowie.

---

## 8. Matematyka — trzy wzory i tyle

Cała niwelacja techniczna sprowadza się do jednej wielkości pośredniej:
**HI, wysokość celowej** (inaczej: horyzont instrumentu, poziom celowej).

```
(1)  HI       = rzędna repera + odczyt wstecz
(2)  H punktu = HI − odczyt wprzód
(3)  odczyt zadany = HI − rzędna projektowa      ← wzór roboczy brygadzisty
```

- **odczyt wstecz (w)** — na łacie stojącej na punkcie o **znanej** rzędnej,
- **odczyt wprzód (p)** — na łacie na punkcie **wyznaczanym**,
- **przewyższenie** Δh = w − p.

**Dopóki nie ruszysz statywu, HI jest stałe.** Dlatego każdy kolejny punkt to
jedno odejmowanie — i dlatego opłaca się ustawić instrument raz, a porządnie.

### Wzór (3) w praktyce

To jest ta operacja, którą robi się dziesiątki razy dziennie: *ile ma pokazać
łata, żeby dno kanału wyszło na rzędnej projektowej.*

```
reper o rzędnej          85.200 m n.p.m.
odczyt wstecz             1.432 m
HI = 85.200 + 1.432   =  86.632 m n.p.m.

rzędna projektowa dna    82.760 m n.p.m.
odczyt zadany = 86.632 − 82.760 = 3.872 m
```

Stawiasz łatę na dnie wykopu:

| Odczyt | Znaczenie |
|---|---|
| **= 3.872** | dno na projekcie ✓ |
| **> 3.872** (np. 3.95) | łata stoi **niżej** → wykop **przegłębiony**, trzeba dosypać i zagęścić |
| **< 3.872** (np. 3.80) | łata stoi **wyżej** → **za płytko**, dobrać gruntu |

Ten kierunek jest kontrintuicyjny i dlatego kalkulator wypisuje go słownie,
a nie samą liczbą.

### Kontrola wykonalności

Zanim ktokolwiek zejdzie z łatą do wykopu, warto sprawdzić, czy pomiar w ogóle
da się wykonać z tego stanowiska:

- **odczyt zadany < 0** → celowa przebiega **poniżej** punktu docelowego.
  Z tego stanowiska go nie zobaczysz — przenieś niwelator wyżej albo nawiąż się
  do wyższego repera.
- **odczyt zadany > 4 m** → wychodzi poza długość łaty. Potrzebne stanowisko
  pośrednie (punkt przejściowy).

Oba przypadki moduł zgłasza jawnie (`wykonalne: false` + opis).

---

## 9. Ciąg niwelacyjny i kontrola błędu

Gdy reper jest daleko od miejsca robót, przenosi się wysokość **ciągiem** —
przez punkty pośrednie (przejściowe). Ciąg powinien być:

- **nawiązany** — od jednego repera do drugiego, albo
- **zamknięty** — wraca do punktu wyjścia.

Suma przewyższeń w ciągu zamkniętym powinna wynosić zero. To, co wyjdzie
naprawdę, to **odchyłka zamknięcia** `f_h`.

Dla **niwelacji technicznej** przyjmuje się dopuszczalną odchyłkę:

```
f_dop = ±20 mm × √L        (L — długość ciągu w kilometrach)
```

Np. dla ciągu 0.5 km: `f_dop = 20 × 0.707 = 14 mm`.

⚠️ Ta wartość jest wartością typową dla niwelacji technicznej. **Specyfikacja
kontraktowa (SST) może narzucać ostrzejszą** — przed odbiorem trzeba sprawdzić,
co stoi w dokumentach tego konkretnego zadania. Moduł liczy wg powyższego wzoru
i zwraca zarówno odchyłkę, jak i próg, więc łatwo podmienić kryterium.

Jeśli odchyłka mieści się w granicy — rozrzuca się ją proporcjonalnie do długości
odcinków. Jeśli nie — pomiar trzeba powtórzyć; szukanie „która liczba jest zła"
zwykle kończy się gorzej niż ponowne przejście ciągu.

---

## 10. Dane, których potrzeba do wytyczenia odcinka kanału

Zebrane w jednym miejscu — to jest dokładnie zakres, jaki narzędzie wyciąga
z dokumentacji:

**Dla obiektu (studnia / wpust / wylot):**
1. kod (`D155`),
2. rzędna dna kanału,
3. rzędna dna studni (`Rz.d.`) — do kopania,
4. rzędna terenu projektowanego,
5. zagłębienie,
6. średnica studni (DN1200 / DN1500 / DN2500),
7. rzędne i średnice wszystkich wlotów.

**Dla odcinka (`Wyl101–D155`):**
1. obiekt początkowy i końcowy,
2. długość [m],
3. średnica rury Ø [mm],
4. spadek [‰],
5. rzędne dna na obu końcach,
6. materiał i klasa sztywności (SN8 / SN10 / SN12).

**Dla pomiaru:**
1. reper i jego rzędna,
2. odczyt wstecz,
3. rzędna docelowa.

---

## 11. Czego świadomie nie robię

- **Nie oceniam, czy projekt jest poprawny.** Narzędzie odczytuje i liczy;
  minimalne spadki, przykrycia i klasy rur są decyzją projektanta.
- **Nie zakładam układu wysokościowego.** Rzędne wchodzą i wychodzą takie,
  jakie są w dokumentacji.
- **Nie ukrywam rozbieżności.** Gdy rysunek nie zgadza się z arkuszem albo
  spadek nie zgadza się z rzędnymi, import zapisuje to jako ostrzeżenie —
  jest ich obecnie 67 z PDF i 41 z porównania PDF↔XLSX. To lista miejsc do
  sprawdzenia w dokumentacji, a nie błąd programu.

---

## Powiązane

- `02-analiza-profile-scalone.md` — jak czytam plik `Profile Scalone.pdf`
- `03-model-danych.md` — schemat bazy i reguły mapowania
- Kod: `app/services/leveling.py`, testy: `tests/test_niwelacja.py`
