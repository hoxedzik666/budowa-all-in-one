# Przelicznik rur

> **Wykonawca ma na budowie rury w dwóch długościach handlowych: 3 m i 6 m.**
> Każda średnica z arkusza `RURY` występuje w obu wariantach.

Kod: [`app/services/rury.py`](../../app/services/rury.py) ·
testy: [`tests/test_rury.py`](../../tests/test_rury.py)

---

## Słownictwo

Te trzy pojęcia trzeba trzymać oddzielnie, bo w tabelce stoją obok siebie:

| Pojęcie | Znaczenie |
|---|---|
| **docinka** | kawałek, który **faktycznie idzie do wykopu** — odcinany z całej rury |
| **odpad** | to, co z tej rury **zostaje** po odcięciu docinki |
| **cięcie** | jedna operacja przecięcia rury |

Zawsze zachodzi: **docinka + odpad = długość całej rury, z której cięto.**

Przykład: odcinek 20,5 m z rur 3 m → 6 rur całych (18 m) + jedna docięta do
**2,5 m**. Docinka = 2,5 m, odpad = 0,5 m, cięć = 1, sztuk = 7.

---

## Jaką długość przyjmujemy

**Oś–oś, wprost z profilu.** Rysunek podaje odległość między osiami studni
(np. `Wyl101–D155` = 20,5 m) i tak samo liczy przedmiar projektanta — dzięki
temu wynik zgadza się z zestawieniem materiałowym. Fizyczne wcięcia w ścianki
studni pokrywa naturalny zapas z zaokrąglenia do pełnych rur.

---

## Trzy warianty

### Same 3 m
```
n = ceil(L / 3)
```

### Same 6 m
```
n = ceil(L / 6)
```

### Mieszany — najmniej sztuk
Przegląd zupełny wszystkich kombinacji `(n₆, n₃)`, wybór według klucza:

```
1. najmniejsza liczba sztuk
2. przy remisie — najmniejszy odpad
```

Zakres jest mały (kilkanaście sztuk), więc przegląd zupełny jest tańszy
i pewniejszy niż heurystyka typu „bierz największe, potem resztę”.

**Dlaczego akurat najmniej sztuk:** każda rura to jedno złącze. Mniej złączy =
szybszy montaż i mniej miejsc, w których może zacząć przeciekać.

---

## Przykłady liczbowe

### `Wyl101 – D155`, 20,5 m, Ø500

| Wariant | Rury | Sztuk | Materiał | Docinka | Odpad | Cięć |
|---|---|---|---|---|---|---|
| same 3 m | 7 × 3 m | 7 | 21,0 m | 2,5 m | 0,5 m | 1 |
| same 6 m | 4 × 6 m | 4 | 24,0 m | 2,5 m | 3,5 m | 1 |
| **mieszany** ★ | **3 × 6 m + 1 × 3 m** | **4** | **21,0 m** | **2,5 m** | **0,5 m** | **1** |

Mieszany daje tyle samo sztuk co „same 6 m”, ale **3 m mniej odpadu**.

### 9,0 m, Ø200 — mieszany wygrywa liczbą sztuk

| Wariant | Rury | Sztuk | Odpad |
|---|---|---|---|
| same 3 m | 3 × 3 m | 3 | 0,0 m |
| same 6 m | 2 × 6 m | 2 | 3,0 m |
| **mieszany** ★ | **1 × 6 m + 1 × 3 m** | **2** | **0,0 m** |

### 78,5 m, Ø500 — remis na sztukach, rozstrzyga odpad

| Wariant | Rury | Sztuk | Odpad |
|---|---|---|---|
| same 6 m | 14 × 6 m | 14 | 5,5 m |
| **mieszany** ★ | **13 × 6 m + 1 × 3 m** | **14** | **2,5 m** |

### 2,5 m — odcinek krótszy niż najkrótsza rura

Cała robota to jedna docinka: 1 × 3 m docięta do 2,5 m, odpad 0,5 m.
Narzędzie wypisuje wtedy jawną uwagę.

---

## Średnice: profil ≠ katalog

Rury PRAGMA opisane są **średnicą zewnętrzną (OD)**, a profil podaje nominalną.
Dla większości średnic to ta sama liczba, ale nie dla wszystkich:

| Profil Ø | Katalog OD |
|---|---|
| 200, 250, 400, 500, 1000 | bez zmian |
| **300** | **315** |
| **600** | **630** |

Bez tego przeliczenia odcinki Ø300 i Ø600 nie znalazłyby żadnej pozycji
w arkuszu materiałowym.

**Kontrola poprawności** — sumy długości z profili vs katalog:
Ø200 = 2157,4 m wobec 2157 m, Ø1000 = 16,0 m wobec 16 m. Zgodność co do metra.

---

## Skąd bierze się klasa SN

Arkusz ma tę samą średnicę w kilku klasach sztywności (SN8 / SN10 / SN12).
Odcinek nie ma zapisanej klasy wprost — projektant notuje ją w **uwagach
obiektu** (`SN8`, `rura SN10`). Serwis czyta uwagi obu końców odcinka; gdy nic
nie znajdzie, pokazuje wszystkie pozycje danej średnicy i zostawia wybór
człowiekowi.

---

## Katalog rur w bazie

19 pozycji rurowych w 7 średnicach, każda w wariancie 3 m i 6 m:

```
OD200  SN10, SN12      OD250  SN10        OD315  SN8
OD400  SN8, SN10       OD500  SN8, SN10   OD630  SN8
OD1000 SN10
```

Parsowanie idzie **z nazwy pozycji**, nie z kolumny `DŁUGOŚĆ` — ta bywa pusta:

```
"PP Rura kanal. SN 8 500/3 CZ/SZ OD PRAGMA"  →  OD500, sztuka 3 m, SN8
```

Wzorzec `(\d{3,4})/(\d{1,2})` jest celowo zawężony i wymaga słowa „rura”
w opisie — bez tego `Trójnik redukcyjny OD 200/200/160` wyglądałby jak rura
o długości 200 m.

---

## Użycie

**W aplikacji:** `/szukaj?q=D155` → karta odcinka → sekcja *Zapotrzebowanie na rury*.

**Przez API:**
```bash
curl http://localhost:8000/api/odcinek/Wyl101/D155/rury
```

**W kodzie:**
```python
from app.services.rury import przelicz, podsumuj

przelicz(20.5, 500)        # trzy warianty dla jednego odcinka
podsumuj(odcinki)          # zbiorczo dla wielu, w rozbiciu na średnice
```

---

## Ograniczenia

- Liczymy **rury**, nie kształtki. Kolana, trójniki i uszczelki są w arkuszu
  materiałowym, ale nie da się ich przypisać do odcinka bez danych o węzłach.
- Nie uwzględniamy zapasu na uszkodzenia ani na docinki wykorzystywane
  ponownie na innym odcinku — odpad liczony jest per odcinek.
- Wariant „według tego, co dojechało” nie jest liczony; stan dostaw
  (kolumna `DOJECHAŁO`) jest tylko **pokazywany** obok wyniku.
