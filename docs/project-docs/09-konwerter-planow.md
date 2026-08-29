# Konwerter planów sytuacyjnych

> Jak z rysunku bez etykiet zrobić dane, które da się policzyć.

---

## Co udało się ustalić o pliku

`Plany sytuacyjne Scalone.pdf`, 18 arkuszy. Zbadane bezpośrednio, nie z założeń:

| Cecha | Wartość |
|---|---|
| Rodzaj | **czysty wektor** — od 40 tys. do 225 tys. ścieżek na stronę |
| Producent | PDF24 (plik scalony z osobnych arkuszy) |
| Warstwy CAD (OCG) | **brak** — nazwy warstw nie przetrwały eksportu |
| Metadane georeferencji | brak |
| Siatka krzyży współrzędnych | **brak** na żadnej stronie |
| Żywy tekst | legenda, tabelka rysunkowa, `KM:0+080` … `KM:9+860`, `ZR-1`, `ZR-2` |
| Kody obiektów jako tekst | **zero** — 667 unikalnych słów w całym pliku |
| Format arkuszy | prawdziwy rozmiar papieru, skala 1:1000 |
| Układ współrzędnych | `2000/15` + `PL-EVRF2007-NH` → **PL-2000 strefa 5, EPSG:2176** |

Dwa wnioski. Po pierwsze: OCR był najgorszą z możliwych dróg — próbował odczytać
z bitmapy to, co w pliku istnieje jako precyzyjny wektor. Po drugie: kodów
obiektów nie odzyska stamtąd nikt i nic, bo ich tam po prostu nie ma.

---

## Pomysł: styl kreski zamiast nazwy warstwy

Warstwy zniknęły, ale **kolor i grubość kreski zostały**. A legenda na stronie 1
ma żywy tekst tuż obok próbek kresek — więc da się odczytać, jakim stylem
narysowano kanalizację deszczową:

```
"Kanalizacja deszczowa grawitacyjna"  →  kolor (0; 0,722; 0,180), grubość 1,98
```

Tym filtrem przechodzi się cały arkusz. Zamiast zgadywać, co jest napisane,
bierzemy to, co jest narysowane.

### Wynik na całym pliku

```
flask konwertuj-plany
```

```
18 stron  ·  704 polilinie  ·  8 952,9 m sieci  ·  40 etykiet kilometrażu
odcinki w bazie (z profili podłużnych):  7 439,5 m
stosunek: 1,20
```

**Stosunek 1,20 jest w porządku** — arkusze zachodzą na siebie na stykach, więc
przewody przy krawędziach liczą się dwa razy. Gdyby wyszło wyraźnie poniżej 1,0,
znaczyłoby to, że filtr stylu czegoś nie łapie; komenda wypisuje tę liczbę
właśnie po to.

---

## Jak to działa krok po kroku

`app/services/plan_wektor.py`

1. **Filtr stylu** — z `page.get_drawings()` biorę ścieżki o kolorze i grubości
   z legendy, i z nich same odcinki linii.
2. **Przyciąganie końców** — końce przyciągam do siatki 0,6 pt (≈ 21 cm
   w terenie: mniej niż średnica najmniejszej studni, więcej niż błędy
   zaokrągleń w pliku). Bez tego dwie kreski stykające się „prawie" nie
   połączyłyby się w jedną polilinię.
3. **Sklejanie w polilinie** — wierzchołek stopnia 2 to załamanie trasy, idziemy
   przez niego dalej. Stopień 1 (koniec przewodu) albo 3+ (rozgałęzienie) kończy
   polilinię — tam w terenie stoi studnia, wpust albo wylot.
4. **Obwody zamknięte** — pętla nie ma żadnego wierzchołka o stopniu innym niż 2,
   więc trzeba ją zacząć od dowolnego punktu. Inaczej przepadłaby bez śladu.
5. **Odsiew drobiazgów** — poniżej 0,5 m to zwykle groty strzałek, nie przewody.

### Skala

Arkusze są w prawdziwym rozmiarze papieru, skala 1:1000:

```
1 pt = 1/72 cala = 0,352778 mm na papierze = 0,352778 m w terenie
```

To przeliczenie jest ścisłe, nie przybliżone.

---

## Kilometraż — bez OCR-u

`KM:5+814` i podobne to **żywy tekst**: 124 wystąpienia na 8 stronach, 40 po
odsianiu powtórzeń. Konwerter wyciąga je razem z pozycją i zamienia na metry
(`KM:5+814` → 5814 m). To domyka prośbę z etapu 2 o kilometraż z planów —
przynajmniej tam, gdzie projektant go podpisał.

---

## Czego konwerter NIE robi

**Nie przypisuje kodów obiektów.** Wycięte polilinie to geometria bez nazw —
`D155` nie jest na planie zapisane w żadnej postaci. Który przewód jest którym
odcinkiem, wiadomo dopiero po wskazaniu pozycji na mapie
(`/mapa`, tryb „Wskaż obiekt") albo po georeferencji ([`10`](10-georeferencja.md)).

Rozważałem automatyczne dopasowanie grafu wyciętego z rysunku do topologii
z profili — długości odcinków są niemal unikalnym odciskiem. Problem: ponad
200 przykanalików ma po ~3,4 m, więc dla nich dopasowanie byłoby losowe.
Przy 47% trafności i braku sposobu odróżnienia trafienia od pomyłki taka funkcja
szkodziłaby bardziej, niż pomagała.

---

## Wydajność i cache

Wycięcie jednej strony to kilka sekund, całego pliku **ponad dwie minuty** —
za długo na żądanie HTTP. Dlatego robi się to raz komendą, a wynik ląduje
w `data/exports/siec/strona-NN.json` (120 kB na cały plan). Widoki i eksporty
czytają gotowy plik.

```bash
flask konwertuj-plany                    # wszystkie strony
flask konwertuj-plany --strony 5,9,13    # wybrane
```

---

## Eksport

| Format | Endpoint | Do czego |
|---|---|---|
| GeoJSON | `/mapa/eksport/<nr>.geojson` | QGIS, geodeta |
| DXF | `/mapa/eksport/<nr>.dxf` | CAD |
| CSV | `/mapa/eksport/<nr>.csv` | węzły do tyczenia z tachimetru |
| `.pgw` | `/mapa/eksport/<nr>.pgw` | plik świata do PNG (tylko po georeferencji) |

**Każdy plik mówi w środku, w jakim jest układzie.** Bez georeferencji są to
współrzędne strony przeliczone na metry przez skalę — i tak jest napisane wprost
w nagłówku GeoJSON-a i w pierwszym wierszu CSV. To nie jest ozdobnik: pomylenie
współrzędnych strony z państwowymi kosztowałoby dzień pracy geodety.

DXF piszemy sami, w wersji R12. Format jest wiekowy i gadatliwy, ale czyta go
każdy program CAD bez wyjątku, a cały zapis to kilkadziesiąt linii — mniej niż
koszt kolejnej zależności.

---

## A co z OCR-em

`app/services/plan_ocr.py` i komenda `flask ocr-plany` **zostają jako droga
historyczna**. Nie mają już zastosowania produkcyjnego: cztery metody OCR-u dały
zero odczytanych kodów, bo etykiety są krzywymi na gęstym rysunku. Opis, co
dokładnie próbowano i dlaczego nie wyszło, jest w [`04-ocr-planow.md`](04-ocr-planow.md).
