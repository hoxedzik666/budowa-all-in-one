# Instrukcja obsługi

> Dla kierownika budowy i brygadzisty. Bez żargonu programistycznego.

---

## Najczęstsze zadanie: „co mam na odcinku przy D155”

1. Wpisz **`D155`** w pole wyszukiwania (górny pasek albo strona **Szukaj**).
2. Dostajesz komplet:

**Nagłówek obiektu** — pięć liczb, które są potrzebne najczęściej:

| Kafelek | Co znaczy |
|---|---|
| Rz. dna kanału | spód rury — na tę rzędną układa się kanał |
| Rz. dna studni | dno osadnika/piaskownika — **do tego kopie koparka** |
| Teren proj. | poziom terenu po robotach |
| Zagłębienie | teren projektowany − rzędna dna kanału |
| Głęb. wykopu | teren projektowany − dno studni |

**Karta każdego odcinka** z udziałem tego obiektu zawiera:

- rysunek profilu podłużnego (linia dna i linia terenu, z rzędnymi),
- tabelkę: długość, średnica, spadek w ‰ i %, rzędne obu końców,
- obiekty na końcach z głębokością wykopu,
- **zapotrzebowanie na rury w trzech wariantach**,
- pozycje z arkusza materiałowego wraz ze stanem dostaw,
- wycinek planu sytuacyjnego (jeśli wskazano pozycję — patrz niżej).

---

## Odczytanie tabeli rur

> Wykonawca ma rury **3 m i 6 m**.

| Kolumna | Co znaczy |
|---|---|
| Rury | ile sztuk i jakiej długości |
| Sztuk | łączna liczba rur do zabrania |
| Materiał | ile metrów trzeba wziąć z magazynu (z odpadem) |
| **Docinka** | kawałek, który **idzie do wykopu** — trzeba go odciąć |
| **Odpad** | co z tej rury **zostaje** |
| Cięć | ile razy trzeba przeciąć |

Wariant oznaczony **gwiazdką** daje najmniej sztuk (przy remisie — mniej odpadu).
Mniej sztuk = mniej złączy = szybszy montaż.

**Przykład** — `Wyl101–D155`, 20,5 m, Ø500:

```
same 3 m     7 × 3 m               21,0 m   docinka 2,5 m   odpad 0,5 m
same 6 m     4 × 6 m               24,0 m   docinka 2,5 m   odpad 3,5 m
mieszany ★   3 × 6 m + 1 × 3 m     21,0 m   docinka 2,5 m   odpad 0,5 m
```

Czytaj to tak: bierzesz 3 całe rury 6-metrowe, czwartą (3 m) docinasz do 2,5 m.
Zostaje 0,5 m odpadu.

Szczegóły: [`03-przelicznik-rur.md`](03-przelicznik-rur.md).

---

## Wytyczenie rzędnej niwelatorem

Strona **Niwelator** albo przycisk *Wytycz* przy obiekcie.

1. **Stanowisko** — wybierz reper z listy (rzędna podstawi się sama) albo wpisz
   ją ręcznie, i podaj **odczyt wstecz** na reperze.
2. **Cel** — wpisz kod obiektu i wybierz, czy celujesz w *dno kanału*, czy
   w *dno studni*.
3. Program poda **odczyt zadany** — tyle ma pokazać łata, żeby wyszło na projekt.

Jeśli podasz też **odczyt zmierzony**, dostaniesz ocenę słowną:

| Sytuacja | Znaczenie |
|---|---|
| odczyt = zadany | dno na projekcie |
| odczyt **większy** | łata stoi niżej → **przegłębione**, dosypać i zagęścić |
| odczyt **mniejszy** | łata stoi wyżej → **za płytko**, dobrać gruntu |

Program ostrzeże też, gdy pomiar **nie jest wykonalny** z tego stanowiska —
gdy celowa biegnie poniżej punktu albo odczyt wychodzi poza 4-metrową łatę.

---

## Plany sytuacyjne

Mapa ma płynne przybliżanie, przesuwanie i podziałkę. W prawym górnym rogu
wybiera się skalę (1:250 … 1:5000) — przydaje się przy drukowaniu wycinka.

### Warstwy

| Warstwa | Co pokazuje |
|---|---|
| Wskazane obiekty | pozycje, które ktoś wskazał ręcznie |
| Sieć wycięta z rysunku | przewody odczytane z wektora — **bez nazw** |
| Kilometraż | podpisy `KM:x+yyy` odczytane z rysunku |
| Repery z osnowy | pojawiają się dopiero po związaniu arkusza z terenem |

### Wskazanie obiektu

Kody obiektów są na planie krzywymi, nie tekstem — program nie odczyta ich sam.
Pozycję wskazuje się raz:

1. **Mapa** → wybierz arkusz → tryb **Wskaż obiekt**.
2. Wpisz kod, np. `D155`, i kliknij w mapę tam, gdzie obiekt leży.

Od tej chwili przy odcinku pojawia się wycinek mapy z zaznaczeniem.

### Związanie arkusza z terenem (dwie kotwice)

Żeby mapa zaczęła podawać prawdziwe współrzędne, a repery same wskoczyły
na plan:

1. Tryb **Kotwica**, wpisz nazwę repera z osnowy (np. `o41`).
2. Kliknij ten reper na mapie. Powtórz dla drugiego.
3. Trzeci reper służy do sprawdzenia — **dwa zawsze pasują idealnie**, więc
   dopiero trzeci coś mówi.

Program pokazuje skalę (musi wyjść ok. 1:1000), obrót i odchyłkę. Skala rzędu
1:760 oznacza, że któreś wskazanie trafiło w zły punkt.

Szczegóły: [`10-georeferencja.md`](10-georeferencja.md).

---

## Sprawdzenie danych w oryginale

Na stronie profilu i na karcie odcinka jest przycisk **„Sprawdź w oryginale"**.
Program wycina z `Profile Scalone.pdf` dokładnie ten fragment — razem z kolumną
podpisów pasm, żeby dało się przeczytać, która liczba jest która — i pokazuje go
obok danych z aplikacji.

Konwersja rusza **dopiero po kliknięciu**. Wynik można pobrać jako PDF; jest
wektorowy, więc da się go powiększać i wydrukować w jakości oryginału.

---

## Dziennik wykonawczy

Po ułożeniu rury wpisz rzędną odczytaną z niwelatora — na karcie odcinka
(**Wpisz pomiar z niwelatora**) albo na `/wykonanie`.

Program od razu podaje:

- **odchyłkę od projektu** i czy mieści się w tolerancji
  (dno kanału ± 2 cm, dno studni ± 3 cm, teren ± 5 cm),
- po dwóch pomiarach — **rzeczywisty spadek** i porównanie z projektowym,
- ostrzeżenie, gdyby woda miała płynąć pod górę.

**Pomiar nie nadpisuje projektu.** To osobny wpis z datą i autorem, więc zawsze
wiadomo, co zaprojektowano, a co zbudowano.

---

## Praca bez zasięgu

Aplikację można zainstalować na telefonie (przeglądarka proponuje „Dodaj do
ekranu głównego"). Raz otwarte strony działają potem **bez sieci**.

**Przed wyjazdem na budowę otwórz karty odcinków, nad którymi będziesz
pracować.** To, co raz zobaczysz przy zasięgu, zostaje w telefonie. Przy braku
sieci na górze pojawia się pasek ostrzegawczy.

Czego nie da się zrobić offline: zapisać pomiaru ani się zalogować.

### Kody QR

`/qr` drukuje naklejki na studnie — skan telefonem otwiera kartę obiektu.
Kod ma podwyższoną korekcję błędów, więc da się go odczytać także zachlapany.

---

## Karta odcinka do druku

Przycisk **Karta do druku** na karcie odcinka daje jedną kartkę A4 do teczki:
profil, rzędne, głębokości wykopu, warianty pocięcia rur i pustą tabelę na
wpisanie pomiarów ołówkiem.

---

## Pozostałe widoki

| Widok | Do czego |
|---|---|
| **Pulpit** | ile czego jest, długość sieci wg średnic, ostatnie importy |
| **Odcinki** | wszystkie odcinki; żółte wiersze = spadek z rysunku nie zgadza się z rzędnymi |
| **Obiekty** | wszystkie węzły, filtr po typie |
| **Profile** | wszystkie profile podłużne z arkuszy |
| **Osnowa** | 151 reperów z rzędnymi |
| **Materiały** | arkusz RURY: projekt, dostawy, WZ, czego brakuje |
| **Wykonanie** | dziennik as-built: pomiary, odchyłki, rzeczywiste spadki |
| **Kody QR** | naklejki na studnie do wydruku |
| **Importy** | co i kiedy wczytano, **rozbieżności** i **odcinki do sprawdzenia** |

---

## Czemu ufać, a co sprawdzić

**Można ufać:** rzędnym, długościom, średnicom i spadkom odczytanym z profili —
kontrola na 900+ węzłach wykazała zgodność z niezmiennikiem
`zagłębienie = teren − dno` w ponad 99% przypadków.

**Warto sprawdzić w dokumentacji:**
- **5 odcinków oznaczonych na czerwono** — mają w dokumentacji długość 0,00 m
  albo spadek 31%. Program ostrzega o nich przy każdej próbie policzenia
  materiału. Nie zgadujemy poprawnych wartości;
- **57 odcinków z rozjazdem spadku** — spadek z rysunku nie zgadza się z tym
  wyliczonym z rzędnych o więcej niż 5‰;
- **41 rozbieżności PDF ↔ Excel**, w tym cztery powyżej 2 m
  (`Wp428` różni się o **7 m**). Jedno ze źródeł jest nieaktualne — narzędzie
  tego nie rozstrzyga, tylko wskazuje.

Pełny przegląd: `flask audyt-danych` oraz [`11-audyt-danych.md`](11-audyt-danych.md).

**Czego narzędzie nie robi:** nie ocenia poprawności projektu. Minimalne spadki,
przykrycia i klasy rur to decyzja projektanta.
