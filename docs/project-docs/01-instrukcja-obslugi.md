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

## Plany sytuacyjne i wskazywanie pozycji

Etykiety na planach są zamienione na krzywe, więc program **nie odczyta ich sam**
(dlaczego — [`04-ocr-planow.md`](04-ocr-planow.md)). Pozycję wskazuje się raz:

1. Wejdź na **Mapa**, wybierz arkusz.
2. Wpisz kod obiektu, np. `D155`.
3. Kliknij **Wskaż pozycję**, potem kliknij w mapę tam, gdzie obiekt leży.

Od tej chwili przy odcinku pojawia się wycinek mapy z zaznaczeniem, a odległości
do sąsiadów liczą się automatycznie.

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
| **Importy** | co i kiedy wczytano oraz **wszystkie znalezione rozbieżności** |

---

## Czemu ufać, a co sprawdzić

**Można ufać:** rzędnym, długościom, średnicom i spadkom odczytanym z profili —
kontrola na 900+ węzłach wykazała zgodność z niezmiennikiem
`zagłębienie = teren − dno` w ponad 99% przypadków.

**Warto sprawdzić w dokumentacji:**
- **67 ostrzeżeń** z odczytu profili (zakładka *Importy*) — głównie studnie,
  do których rury wchodzą na różnych rzędnych;
- **41 rozbieżności PDF ↔ Excel**, w tym cztery powyżej 2 m
  (`Wp428` różni się o **7 m**). Jedno ze źródeł jest nieaktualne — narzędzie
  tego nie rozstrzyga, tylko wskazuje.

**Czego narzędzie nie robi:** nie ocenia poprawności projektu. Minimalne spadki,
przykrycia i klasy rur to decyzja projektanta.
