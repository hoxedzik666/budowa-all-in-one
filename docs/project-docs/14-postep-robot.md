# Postęp robót: stan odcinków i raporty dzienne

> Od etapu 5 aplikacja nie tylko czyta dokumentację — śledzi, co z niej
> zostało zbudowane.

---

## Ożywienie martwego pola

`Segment.status` i `NetworkObject.status` istniały od etapu 1 z typem
`StatusWykonania(PROJEKT, WYTYCZONY, W_TRAKCIE, WYKONANY, ODEBRANY)` — i nigdy
nie były ustawiane:

```sql
SELECT status, count(*) FROM segment GROUP BY 1;   -- PROJEKT | 649
```

Nie dokładałem nowego pola. Sam zestaw wartości niósł już decyzję projektową:
**WYKONANY i ODEBRANY to dwa osobne stany**, czyli odbiór jest dwustopniowy.

---

## Ścieżka i kto ją przesuwa

```
PROJEKT ──► WYTYCZONY ──► W_TRAKCIE ──► WYKONANY ──► ODEBRANY
            └──────── monter / brygadzista ────┘     └ kierownik ┘
```

Podział przebiega tam, gdzie przebiega na budowie: **zgłosić wykonanie może
każdy, kto tę robotę zrobił — odebrać może tylko kierownik**.

Powrót o krok wstecz jest dozwolony (pomyłka się zdarza) i zapisywany.
Wyjątkiem jest cofnięcie odbioru — to również należy do kierownictwa.

⚠️ Reguła działa **po stronie serwera**. Przycisk odbioru jest monterowi
ukrywany, ale żądanie wysłane z pominięciem strony też zostanie odrzucone.

---

## Historia zamiast nadpisywania

Samo pole `status` pamięta tylko ostatnią wartość, a przy odbiorze pada pytanie
*kto i kiedy*. Każda zmiana zostawia więc wpis w `zmiana_statusu`
(odcinek, poprzedni, nowy, autor, data, uwagi).

Ta sama zasada, co przy pomiarach wykonawczych: **nic nie nadpisujemy,
dokładamy wpisy**.

---

## Ostrzeżenia zamiast blokad

Zgłoszenie odcinka jako wykonanego sprawdza, czy pomiary to potwierdzają:

| Sytuacja | Komunikat |
|---|---|
| brak jakiegokolwiek pomiaru | „nie ma czym potwierdzić wykonania" |
| pomiary poza tolerancją | ile z ilu i **jaka jest największa odchyłka** |
| spadek w złą stronę | „woda popłynie pod górę" z promilami i długością |
| dane odcinka oznaczone jako niepewne | powód z audytu ([`11`](11-audyt-danych.md)) |

**Nie blokujemy.** Na budowie zdarza się zgłosić odcinek przed wpisaniem
pomiarów, a program, który tego zabrania, zostaje ominięty — nie poprawiony.
Ostrzeżenie podaje konkretną liczbę; decyzję podejmuje człowiek.

---

## Widok `/postep`

Pasek postępu całej sieci w metrach, nie w sztukach — bo odcinki mają od 3 do
50 m i liczenie sztuk dałoby mylący obraz.

```
7 439,5 m sieci  ·  wykonane X %  ·  odebrane Y %
```

Domyślnie lista pokazuje **to, co się dzieje** — odcinki poza stanem PROJEKT.
Inaczej pierwsze, co widziałby kierownik, to 649 wierszy „w projekcie".

---

## Warstwa postępu na mapie

`/mapa` → warstwa **Postęp robót**. Odcinek rysuje się jako linia między
wskazanymi pozycjami obu końców, kolorem wg stanu:

| Stan | Kolor |
|---|---|
| w projekcie | szary |
| wytyczony | żółty |
| w trakcie | pomarańczowy |
| wykonany | niebieski |
| odebrany | zielony, grubszy |

### Czego nie zamiatamy pod dywan

Pozycje obiektów wskazuje się ręcznie (kodów nie ma na planie — patrz
[`09`](09-konwerter-planow.md)), więc **większości odcinków narysować się nie da**.
Dziś:

```
odcinki z obu końcami wskazanymi:    62
odcinki z jednym końcem:             89
odcinków razem:                     649
```

Dlatego pod warstwą stoi zdanie w rodzaju *„Narysowano 25 odcinków. Kolejnych 14
nie da się narysować — brakuje wskazanej pozycji drugiego końca."* Pokazanie
pięciu z czterdziestu i przemilczenie reszty byłoby wprowadzaniem w błąd.

Odcinek z **jednym** wskazanym końcem dostaje kółko w tym punkcie z adnotacją,
którego obiektu brakuje — lepsze niż zniknięcie z mapy.

---

## Raporty dzienne

`/raporty` — co brygada zrobiła danego dnia.

Pola idą za papierowym raportem dziennym, bo taki i tak powstaje na budowie:
data, brygada, odcinek, opis, metry, ludzie, sprzęt, pogoda, **przestój z powodem**.

Przestój ma własną rubrykę nie dla statystyki: **udokumentowany przestój bywa
podstawą roszczenia terminowego**, a przypomniany po miesiącu jest bezwartościowy.

Podsumowanie ostatnich 7 dni: metry, dniówki, wpisy, godziny przestoju.

### Jeden formularz zamiast dwóch

Zapisując raport można od razu przestawić stan odcinka. To najczęstszy ruch
końca dnia i nie ma powodu, żeby wymagał dwóch wizyt w aplikacji. Zmiana trafia
do historii z adnotacją, że przyszła z raportu.

### Kto co widzi

Monter widzi **wyłącznie swoje** wpisy. Brygadzista, kierownik i administrator
widzą całą ekipę. To jedyna różnica między monterem a brygadzistą.

Raport bez odcinka jest dozwolony — dowóz materiału i przygotowanie zaplecza też
są pracą.

---

## Dwa źródła prawdy — świadomie

Stan odcinka i pomiary wykonawcze to dwa niezależne zapisy tej samej roboty
i **mogą się rozjechać**. Nie wymuszam zgodności, bo:

- odcinek bywa układany trzy dni, a jednego dnia brygada dotyka czterech odcinków
  — z raportów nie da się wyliczyć stanu,
- stan mówi „gdzie jesteśmy teraz", pomiar mówi „czy wyszło dobrze". To różne
  pytania.

Zamiast blokować, program pokazuje rozbieżność w momencie zgłoszenia.

---

## API

| Endpoint | Zwraca |
|---|---|
| `GET /postep?stan=&szukaj=` | przegląd stanów |
| `POST /postep/<id>/stan` | zmiana stanu odcinka |
| `GET /api/postep/odcinek/<od>/<do>` | stan, następny krok (z uprawnieniem), historia, ostrzeżenia |
| `GET /api/mapa/postep/<nr>?wszystkie=1` | odcinki do narysowania + lista tych, których się nie da |
| `GET /raporty?dzien=&szukaj=` | raporty dzienne |
| `POST /raporty/dodaj` · `POST /raporty/<id>/usun` | operacje na raportach |
| `GET /api/raporty` | raporty widoczne dla zalogowanego + podsumowanie tygodnia |

`/api/postep/odcinek/...` podaje przy każdym kroku, **czy zalogowana osoba może
go wykonać i dlaczego nie** — interfejs nie musi powielać reguł uprawnień.
