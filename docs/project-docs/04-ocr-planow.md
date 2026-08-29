# Plany sytuacyjne — co się udało, a co nie

> Uczciwy zapis próby automatycznego powiązania obiektów z planami sytuacyjnymi.
> Wynik jest w większości **negatywny** i lepiej, żeby było to zapisane wprost,
> niż żeby ktoś za pół roku powtarzał tę samą drogę.

Kod: [`app/services/plan_ocr.py`](../../app/services/plan_ocr.py),
[`app/blueprints/mapa.py`](../../app/blueprints/mapa.py)

---

## Czego chcieliśmy

Po wyszukaniu `D155` pokazać: **kilometraż**, **wycinek mapy z zaznaczonym
odcinkiem** i **najbliższe repery**.

## Dlaczego to nie wychodzi wprost

`Plany sytuacyjne Scalone.pdf` to 18 arkuszy rysunku **wektorowego**, ale:

**1. Wszystkie etykiety są zamienione na krzywe.**
W całym pliku jest **667 unikalnych słów**. Szukane `D155` → **0 trafień**,
`Wyl101` → 0, `Wp65` → 0, znak `Ø` → 0, żaden reper. Prawdziwym tekstem są
tylko: legenda (str. 1), tabelka rysunkowa, nazwy miejscowości, skala `1:1000`
i markery kilometrażowe **drenów** (`KM:4+007`) — które dotyczą odwodnienia
drogi, nie kanalizacji.

Za to na każdej stronie jest **ok. 180 000 ścieżek wektorowych** — to w nich
siedzą napisy, rozłożone na krzywe.

**2. Żaden dostarczony plik nie ma współrzędnych X/Y obiektów.**
`!!_DK29_osnowa_ok_v1.txt` ma X/Y, ale to punkty pomiarowe `o1..o180`, a nie
studnie. `Materiał.xlsx` ma rzędne, nie ma współrzędnych poziomych.

Bez współrzędnych albo bez pozycji na rysunku nie da się policzyć ani kilometra,
ani odległości do repera.

---

## Co próbowaliśmy z OCR

Etykiety **są na rysunku** — widać je gołym okiem po wyrenderowaniu
(`Wyl157`, `D143`, `Wyl67`, `ø500 i=3.9% L=29.5m`). Problem w tym, że:

- leżą **pod kątem** (droga biegnie ukośnie przez arkusz),
- siedzą na **gęstej szrafurze** (wzory kropkowe, linie kolorowe),
- są **małe** — przy 1:1000 etykieta ma kilka punktów wysokości.

Cztery podejścia, wszystkie zweryfikowane pomiarem:

| Podejście | Wynik |
|---|---|
| tesseract `--psm 11`, 300 dpi, kafelki | 5162 tokeny na stronie, **0 prawdziwych etykiet** |
| przegląd obrotów −40°…+40° co 10° | **0 trafień** przy obu trybach `psm` |
| progowanie (110 / 150) + obrót | odzyskane `ø500`, `L=29.5m` (napisy poziome), **0 kodów obiektów** |
| separacja po kolorze wektorów | 6563 z 9799 ścieżek w wycinku jest czarnych — szrafura też; **nie rozdziela** |

Pierwsza wersja „znajdowała” 8 kodów na stronie 9 — wszystkie okazały się
**fałszywe**: `0.6` → `O6`, `0.04` → `O4`, `010` → `O10`. To były wymiary
z rysunku, a nie osadniki. Cyfra zero mylona z literą O. Ta reguła została
z parsera usunięta.

**Wniosek: dla tej dokumentacji OCR nie nadaje się do automatycznego
lokalizowania obiektów.**

---

## Co zrobiliśmy zamiast

### Przeglądarka planów — `/mapa`

Każdy z 18 arkuszy da się obejrzeć i przybliżyć. Renderowanie jest szybkie:
strona @150 dpi w 2,6 s, wycinek @200 dpi w 1,3 s. Wyniki są cache'owane
w `data/exports/mapy/`.

### Ręczne wskazanie pozycji

Wpisujesz kod obiektu, klikasz *Wskaż pozycję*, klikasz w mapę. Współrzędne
w punktach PDF trafiają do tabeli `plan_location` z flagą `zweryfikowane`.

**Od tego momentu działa automatycznie:**
- wycinek mapy przy odcinku (`/mapa/odcinek/<od>/<do>.png`) z zaznaczeniem,
- odległości do sąsiadów, liczone przez skalę rysunku:
  `1 pt = 0,3528 mm na papierze = 0,3528 m w terenie przy 1:1000`.

W praktyce warto wskazać kilkadziesiąt kluczowych węzłów, nie wszystkie 1059.

### Repery — dwie różne rzeczy, jasno rozdzielone

| Co | Kiedy działa |
|---|---|
| **Najbliższe w terenie** | dopiero gdy obiekt i repery mają pozycję na planie; bez tego widok mówi **czego brakuje**, zamiast zgadywać |
| **O zbliżonej rzędnej** | zawsze — to podpowiedź, z którego repera wygodnie się nawiązać, żeby odczyt zmieścił się na 4-metrowej łacie |

Drugie **nie jest** przybliżeniem pierwszego i nigdzie nie jest tak nazywane.

---

## Komenda OCR (gdy chcesz spróbować sam)

```bash
# tylko raport, nic nie zapisuje
docker compose exec web python -m flask ocr-plany --strony 9,13

# zapis znalezionych pozycji do bazy
docker compose exec web python -m flask ocr-plany --zapisz
```

Ręcznie wskazane pozycje mają **pierwszeństwo** — OCR ich nie nadpisze.
Każdy wynik OCR ma zapisaną pewność; poniżej 70 interfejs oznacza go jako
niepewny.

---

## Co odblokowałoby pełną funkcjonalność

W kolejności od najlepszego:

1. **Wykaz współrzędnych obiektów** — plik `kod,X,Y` w rodzaju osnowy.
   W projektach drogowych zwykle istnieje. Daje kilometraż, mapę i najbliższe
   repery **dokładnie**, bez zgadywania.
2. **Plik DWG/DXF** — etykiety są tam tekstem, nie krzywymi.
3. **PDF przed konwersją tekstu na krzywe** — ta sama korzyść.

Do czasu, gdy któryś się pojawi, mapa działa w trybie ręcznego wskazania,
a wszystkie pozostałe funkcje narzędzia (wyszukiwarka, profil, tabelka,
materiały, przelicznik rur, niwelator) są **od tego niezależne**.
