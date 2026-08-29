# Audyt danych — co było zepsute i jak to naprawiono

> Przegląd całego przepływu z plików źródłowych do bazy, przeprowadzony
> zapytaniami do działającej bazy. Każdy punkt ma dowód liczbowy.

---

## Streszczenie

| # | Problem | Skutek | Stan |
|---|---|---|---|
| A1 | Połączenia dublowane przy każdym imporcie | 2442 wiersze zamiast 880 | naprawione |
| A2 | Import profili kasował połączenia z arkusza | kompletność zależała od kolejności komend | naprawione |
| A3 | Ponowny import nie odświeżał rzędnych | poprawka w PDF nigdy nie dotarłaby do bazy | naprawione |
| A4 | Niezmiennik rzędnych łamany na 8 obiektach | zagłębienie nie zgadzało się z rzędnymi | naprawione |
| A5 | 5 odcinków z danymi nie do wykonania | liczyły się do materiału bez ostrzeżenia | oznaczone |
| A6 | Spadek z rzędnych ujemny na 98% odcinków | API zwracało wartości ze znakiem minus | naprawione |
| A7 | „Najbliższe repery" zwracały studnie | funkcja robiła co innego, niż obiecywała | naprawione |
| A8 | Braki w danych źródłowych | — | raportowane |
| A9 | Cache bez limitu, PDF otwierany przy każdym żądaniu | mapa nie do użycia przy zoomie | naprawione |

Kontrola: `flask audyt-danych`

---

## A1. Połączenia dublowane trzykrotnie ⚠️

```sql
SELECT count(*) FROM connection;                    -- 2442
-- unikalnych po naturalnym kluczu:                    771
SELECT zrodlo, count(*) FROM connection GROUP BY 1;
--   XLSX_MATERIAL   2340      (import uruchamiano 3 razy)
--   PDF_PROFIL       102
```

`importuj_xlsx()` czyściła przed wgraniem `MaterialItem`, ale **nie**
`Connection`. Każdy przebieg dokładał komplet od nowa. Karta obiektu i
`/api/szukaj` pokazywały ten sam dopływ trzy razy.

**Naprawa** — trzy warstwy, bo sam kod to za mało:

1. import kasuje własne połączenia (`zrodlo == XLSX_MATERIAL`) na starcie,
2. w obrębie jednego przebiegu pilnuje zbioru naturalnych kluczy — ten sam wlot
   bywa opisany na dwóch profilach (włączenie `Wp466` do `Wyl6` widnieje i na
   profilu wylotu, i wpustu; to jedno połączenie, nie dwa),
3. unikalny indeks `uq_connection_naturalny` w bazie, zakładany przez
   `app/services/schemat.py` **po** odsianiu duplikatów.

Test `test_baza_nie_ma_zdublowanych_polaczen` porównuje liczbę wierszy z liczbą
unikalnych kluczy — dwukrotny `import-xlsx` nie zmienia liczby wierszy.

---

## A2. Import profili kasował cudze dane

`delete(Connection)` bez warunku wywalał także graf połączeń z arkusza
materiałowego. Kompletność danych zależała od kolejności komend, czego nigdzie
nie było napisane.

**Naprawa:** kasujemy tylko `zrodlo == PDF_PROFIL`. `import-wszystko` wymusza
kolejność (osnowa → profile → arkusz), a `import-profile` uruchomiony osobno
wypisuje przypomnienie, żeby po nim przepuścić arkusz.

---

## A3. Ponowny import nie odświeżał danych

Pola obiektów ustawiane były warunkiem `if getattr(ob, pole) is None`, a
`rzedna_dna_kanalu` liczona jako **minimum ze wszystkich profili**. To minimum
kumulowało się przez kolejne przebiegi: raz obniżona rzędna nigdy już nie
wzrosła, choćby rysunek podawał wyższą.

Dziś nieszkodliwe — dane wgrano raz. Przy pierwszej korekcie projektu wyszłaby
cicha, nieodwracalna rozbieżność. To najgorszy rodzaj błędu: taki, którego nikt
nie zauważy.

**Naprawa:** przy `wyczysc=True` pola pochodzące z rysunku wracają do `NULL`
przed ponownym wczytaniem. Kod, typ, wskazane pozycje na planie i pomiary
wykonawcze zostają nietknięte.

---

## A4. Niezmiennik rzędnych

```
zagłębienie = rzędna terenu proj. − rzędna dna kanału
```

Trójka trafia do bazy z trzech niezależnych miejsc rysunku, więc potrafiła się
rozjechać — 8 obiektów, m.in. `Wp217` (zagłębienie 1,20 m przy 4,05 m
wychodzących z rzędnych).

**Naprawa:** po imporcie zagłębienie jest przeliczane z rzędnych — bo rzędne są
mierzone, a zagłębienie jest ich różnicą. Każda poprawka większa niż 2 cm trafia
do ostrzeżeń importu.

Po naprawie: **0 obiektów łamiących niezmiennik.**

---

## A5. Odcinki nie do wykonania

```
Wyl103-Wp66    0,00 m  Ø200   5,0‰    83,500 → 83,540
Wyl120-Wp92    0,00 m         5,0‰    43,580 → 43,590
Wyl222-Wp221   0,00 m  Ø200  24,0‰    82,550 → 82,730
Wp5-Wyl446      brak długości
Wyl253-Wp250   3,50 m  Ø200 314,0‰    84,750 → 85,840   ← spadek 31%
```

**Nie zgadujemy poprawnych wartości.** Odcinek dostaje flagę `podejrzany`
z podanym powodem, a program ostrzega przy każdej próbie policzenia z niego
materiału albo spadku — czerwona ramka na karcie odcinka i osobna sekcja
na `/importy`.

Brygadzista wchodzący w wykop musi wiedzieć, której liczbie nie wolno ufać.

---

## A6. Spadek z rzędnych wychodził ujemny

633 z 647 odcinków ma `rzedna_dna_od < rzedna_dna_do`, bo profile rysuje się
**od wylotu w górę sieci**. To konwencja rysunku, nie błąd danych — ale
`spadek_wyliczony_promile` zwracał wtedy wartość ujemną i taka szła do API.

**Naprawa:** spadek to wielkość bez znaku, więc zwracamy moduł. O zwrocie mówi
osobne pole `kierunek_rysunku` (`z_pradem` / `pod_prad`), które parser i tak
wyliczał — tylko nie wychodziło na wierzch. Doszło też
`rozjazd_spadku_promile`: różnica między spadkiem z rysunku a z rzędnych.

---

## A7. „Najbliższe repery" nie zwracały reperów

Funkcja liczyła odległości po tabeli `plan_location`, a ta wskazuje **wyłącznie
na obiekty sieci**. Repery z osnowy nie miały jak się tam znaleźć, więc na
liście „najbliższych reperów" pojawiały się studnie i wpusty.

**Naprawa:** po georeferencji ([`10`](10-georeferencja.md)) repery liczy się
naprawdę — z X, Y osnowy przeliczonych na arkusz. Do czasu związania arkusza
funkcja mówi wprost, czego brakuje, zamiast podawać coś innego.

---

## A8. Braki w danych źródłowych

Nie są to błędy programu — dokumentacja po prostu tego nie podaje. Kierownik
ma prawo wiedzieć:

```
odcinków bez średnicy         203 z 649
odcinków bez spadku            93
obiektów bez żadnego odcinka   15
obiektów bez rzędnej dna        2
```

**Rozjazd spadku rysunek ↔ rzędne:** 180 z 552 odcinków przekracza 1‰, ale
skupione jest to na krótkich (137 z 295 odcinków poniżej 5 m). To zaokrąglenia:
rzędne mają dokładność 1 cm, więc na 3 m odcinku błąd 0,01 m daje już 3,3‰.
Dlatego próg jest procentowy z podłogą 5‰ — realnie podejrzanych zostaje **57**,
i tylko one trafiają do raportu.

---

## A9. Wydajność

**PDF otwierany przy każdym żądaniu obrazka.** Przy kafelkach mapy — kilkanaście
żądań na jedno przesunięcie — zoom byłby nie do użycia.

Samo trzymanie otwartego dokumentu nie wystarczyło: `page.get_pixmap()` za
każdym razem na nowo przetwarza strumień treści strony. Rozwiązaniem jest
**lista wyświetlania** (`page.get_displaylist()`), budowana raz na stronę:

```
12 kafelków bez listy wyświetlania    5,18 s
12 kafelków z listą wyświetlania      0,21 s      25 razy szybciej
```

To pilnuje test `test_lista_wyswietlania_przyspiesza_kafelki` — dopuszcza
najwyżej 200 ms na kafelek.

**Cache bez limitu.** Katalog map miał 30 MB, kafelki zwielokrotniłyby to
wielokrotnie. Doszło sprzątanie do zadanego limitu, kasujące najdawniej używane
pliki.

---

## Jak to sprawdzić samemu

```bash
flask audyt-danych                       # pełny raport
flask audyt-danych --kategoria ODCINEK_ZEROWY
flask audyt-danych --tylko-raport        # bez zapisywania flag
```

Ten sam walidator uruchamia się automatycznie po każdym imporcie, a jego wynik
ląduje w historii importu i na `/importy`.

Kategorie: `ODCINEK_ZEROWY`, `ODCINEK_BEZ_DLUGOSCI`, `ODCINEK_ZA_DLUGI`,
`SPADEK_POZA_ZAKRESEM` (te cztery blokują odcinek), `ROZJAZD_SPADKU`,
`NIEZMIENNIK_RZEDNYCH` (te dwie tylko ostrzegają).

---

## Uwaga o schemacie bazy

Projekt zakłada schemat przez `db.create_all()`, które **tworzy tylko brakujące
tabele — nie dotyka istniejących**. Nowa kolumna w modelu nie pojawiłaby się
w działającej bazie.

`app/services/schemat.py` trzyma krótką listę zmian **addytywnych**
(`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`), wykonywanych przy
każdym `flask init-db`. Dzięki temu zmiana modelu nie wymaga kasowania bazy
razem z ręcznie wskazanymi pozycjami na planach.

Czego tam **nie** robimy: kasowania kolumn i zmian typów. To zmiany, które mogą
zniszczyć dane — takie idą przez Flask-Migrate, ze świadomą decyzją człowieka.
