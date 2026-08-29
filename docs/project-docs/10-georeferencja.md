# Georeferencja — związanie arkusza z terenem

> Dwa kliknięcia zamieniają rysunek w mapę.

---

## Po co

Do tej pory pozycje na planie były współrzędnymi strony PDF. Wystarczały do
wycięcia mapki i policzenia odległości między dwoma wskazanymi obiektami — ale
nie pozwalały odpowiedzieć na pytanie, które pada na budowie najczęściej:

> *Z którego repera mam się nawiązać przy tej studni?*

Repery z osnowy mają współrzędne X, Y w układzie państwowym. Obiekty na planie
miały współrzędne strony. Dwóch układów nie da się porównać, więc funkcja
„najbliższe repery" w wyszukiwarce **zwracała nie repery, tylko inne wskazane
obiekty** — co było błędem, nie kompromisem (patrz [`11`](11-audyt-danych.md), A7).

Georeferencja łączy te dwa światy.

---

## Dlaczego trzeba wskazać ręcznie

Sprawdziłem plik pod tym kątem. Nie ma w nim **niczego**, z czego dałoby się
odzyskać położenie automatycznie:

- brak warstw OCG i metadanych,
- brak siatki krzyży współrzędnych na którejkolwiek z 18 stron,
- opisy siatki i etykiety punktów są krzywymi, nie tekstem,
- kilometraż jest podpisany, ale odnosi się raz do trasy głównej, raz do dróg
  dojazdowych — bez rozróżnienia w treści napisu.

Zostaje jedna droga: człowiek wskazuje na rysunku punkty, których współrzędne
zna. **Wystarczą dwa.**

---

## Matematyka: przekształcenie Helmerta

Rysunek w skali 1:1000 jest podobieństwem terenu — obrót, przesunięcie i jedna
wspólna skala. Cztery niewiadome, więc dwa punkty wystarczą.

```
Y (wschód) = a·x + b·y + c
X (północ) = b·x − a·y + d          (znak przy y bierze się z tego,
                                     że oś Y w PDF rośnie w dół)

skala  = √(a² + b²)      →  ma wyjść ≈ 0,352778 m/pt
obrót  = atan2(b, a)
```

Rozwiązanie jest zamknięte (wzór Helmerta), bez macierzy i bez `numpy` — przy
czterech niewiadomych przejrzystość jest ważniejsza niż ogólność.

### Dlaczego nie przekształcenie afiniczne

Afiniczne ma sześć niewiadomych: dopuszcza różną skalę w obu osiach i ścinanie.
Dopasowałoby się **lepiej** do niedokładnych wskazań — i właśnie dlatego jest
złym wyborem. Ukryłoby błąd zamiast go pokazać. Helmert, mając tylko cztery
stopnie swobody, nie ma jak zamaskować pomyłki: wychodzi ona natychmiast
w skali albo w odchyłce.

---

## Kontrola jakości

Program pokazuje przy każdym związaniu trzy liczby:

| Liczba | Co znaczy |
|---|---|
| **skala** | musi wyjść ok. 1:1000. Odchyłka ponad 5% oznacza, że któreś wskazanie trafiło w zły punkt |
| **obrót** | sam w sobie nie jest błędem — plany bywają obrócone celowo, gdy trasa idzie ukosem |
| **odchyłka (RMSE)** | ile średnio brakuje do zgodności |

⚠️ **Dwie kotwice zawsze pasują idealnie** — cztery równania, cztery niewiadome,
odchyłka z definicji zero. Ta liczba nic wtedy nie mówi i interfejs pisze o tym
wprost. **Sprawdzianem jest dopiero trzecia kotwica.**

Dlatego kryterium wiarygodności opiera się przede wszystkim na skali: pomylony
reper daje skalę w rodzaju 1:760, i to widać od razu, nawet przy dwóch punktach.

---

## Jak używać

`/mapa` → tryb **Kotwica**

1. Wpisz nazwę repera z osnowy (np. `o41`) — współrzędne program weźmie z bazy.
   Albo wpisz X i Y wprost, jeśli masz punkt spoza osnowy.
2. Kliknij ten punkt na mapie.
3. Powtórz dla drugiego. Po drugim pojawia się wynik dopasowania.
4. Trzeci punkt (zalecany) służy do kontroli.

Od tego momentu:

- kursor nad mapą pokazuje **X i Y w PL-2000/5**,
- **repery z osnowy pojawiają się na planie same** — warstwa „Repery z osnowy",
  bez klikania,
- eksport GeoJSON/DXF/CSV wychodzi w układzie państwowym,
- dostępny jest plik świata `.pgw` — PNG arkusza otwiera się w QGIS na swoim
  miejscu.

Arkusz bez kotwic działa dokładnie jak wcześniej. Nic nie przestaje działać.

---

## Model danych

```
plan_georef   strona_id (unikalne), ey_x ey_y ey_0 nx_x nx_y nx_0,
              skala_m_na_pt, obrot_stopnie, rmse_m, liczba_kotwic, uklad
plan_anchor   strona_id, punkt_id (reper z osnowy albo NULL),
              x_pt y_pt, x_gis y_gis, nazwa
```

Przekształcenie przelicza się od nowa po każdej zmianie kotwic. Poniżej dwóch
kotwic zapis jest **kasowany** — lepiej brak wyniku niż wynik zmyślony.

---

## Endpointy

| Endpoint | Do czego |
|---|---|
| `POST /api/mapa/kotwica` | wskaż punkt o znanych współrzędnych |
| `DELETE /api/mapa/kotwica/<id>` | usuń kotwicę i przelicz |
| `GET /api/mapa/wspolrzedne/<nr>?x_pt=&y_pt=` | punkt rysunku → X, Y |
| `GET /api/mapa/repery/<nr>` | repery z osnowy naniesione na arkusz |
| `GET /mapa/eksport/<nr>.pgw` | plik świata |

---

## Układ współrzędnych

**PL-2000 strefa 5, EPSG:2176** (południk osiowy 15° E). Tabelka rysunku podaje
`2000/15`, co nazywa południk, nie numer strefy — plik osnowy potwierdza:
X ≈ 5 771 000, Y ≈ 5 503 800, a prefiks „5" we współrzędnej Y (wschodniej) wskazuje strefę 5.
Wysokości: PL-EVRF2007-NH.
