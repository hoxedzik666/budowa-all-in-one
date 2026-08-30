# Przeniesienie na Androida — analiza i plan

> Stan: **analiza wykonana, plan zrewidowany**. Aplikacja powstała w etapie 6 —
> patrz [`15-aplikacja-android.md`](15-aplikacja-android.md).
>
> ⚠️ **Zalecana tu kolejność 1 → 3 okazała się niewykonalna.** TWA wymaga HTTPS
> i Digital Asset Links pod publiczną domeną, a serwer stoi po HTTP w sieci
> budowy. Poszedł więc **wariant 2 (Capacitor)**, który takiego wymogu nie ma.
> TWA wraca do gry razem z HTTPS. Reszta tego dokumentu pozostaje aktualna.

---

## Na czym polega problem

Aplikacja to trzy rzeczy, z których **żadna nie uruchomi się na telefonie**:

| Składnik | Do czego | Czemu nie na Androidzie |
|---|---|---|
| Flask renderujący HTML | wszystkie widoki | serwer, nie klient |
| PostgreSQL 16 | baza | brak sensownego portu na Androida |
| PyMuPDF | kafelki mapy, wycinki profili | biblioteka natywna, 32 MB PDF do przemielenia |

Wniosek jest jednoznaczny: **APK będzie klientem, nie kopią aplikacji.**
Jedyne otwarte pytanie brzmi — ile potrafi bez zasięgu.

To nie jest ograniczenie tego projektu. Każde narzędzie tej klasy (Autodesk
Build, Fieldwire, Procore) działa tak samo: serwer trzyma dane, telefon je
pokazuje i buforuje.

---

## Co mówią liczby

Zmierzone na tym projekcie, nie oszacowane:

```
obiekty + odcinki w bazie             1,5 MB   →  jako JSON ok. 0,6 MB
osnowa (151 punktów) + materiały    < 0,2 MB
Profile Scalone.pdf                   1,6 MB   →  zmieści się na telefonie
Plany sytuacyjne Scalone.pdf         32,0 MB   →  to jest ciężka część
biblioteki front-endu (vendor/)       1,4 MB
```

**Dane robocze mieszczą się na telefonie bez trudu.** Cała sieć — 1059 obiektów,
649 odcinków, rzędne, spadki, materiały — to poniżej megabajta JSON-a. Problemem
są wyłącznie plany sytuacyjne.

Dlatego mapa dzieli się na dwa przypadki:

- **z zasięgiem** — kafelki z serwera, tak jak teraz,
- **bez zasięgu** — kafelki pobrane wcześniej dla wybranego arkusza. Jeden
  arkusz w przydatnym przybliżeniu to rząd kilkudziesięciu megabajtów, więc
  pobiera się je świadomie, przed wyjazdem — nie „na wszelki wypadek".

---

## Trzy warianty

### Wariant 1 — TWA (Trusted Web Activity)

Android otwiera istniejące PWA bez paska przeglądarki. **PWA już działa**
(etap 4: manifest, service worker, ikony), więc pracy zostaje niewiele.

| | |
|---|---|
| Nakład | ~1 dzień |
| Daje | APK w launcherze, ikonę, pełny ekran, całość obecnego interfejsu |
| Nie daje | nic ponad to, co już umie PWA |
| Wymaga | **HTTPS** oraz Digital Asset Links (`assetlinks.json` na serwerze) |

Techniki: Bubblewrap (`@bubblewrap/cli`) generuje projekt Androida z manifestu
PWA. Podpisanie kluczem i APK gotowy.

### Wariant 2 — Capacitor

WebView plus most do funkcji telefonu.

| | |
|---|---|
| Nakład | 1–2 tygodnie |
| Daje | **aparat** (zdjęcie wykopu przy pomiarze), **GPS** (gdzie stoję względem planu — po georeferencji z etapu 4 da się to pokazać na mapie), skaner QR bez przeglądarki, powiadomienia o przydzielonym zadaniu |
| Nie daje | niezależności od serwera |

GPS jest tu największą wartością i wynika wprost z tego, co już zbudowano:
arkusz związany z układem PL-2000/5 potrafi przeliczyć pozycję z telefonu na
punkt na rysunku. Bez georeferencji byłby bezużyteczny.

### Wariant 3 — offline-first z synchronizacją

Lokalna kopia danych roboczych, kolejka zmian, synchronizacja po powrocie zasięgu.

| | |
|---|---|
| Nakład | 3–4 tygodnie |
| Daje | **realną pracę bez zasięgu** — pomiary, raporty i zmiany stanu zapisują się lokalnie i dojeżdżają później |
| Kosztuje | rozstrzyganie konfliktów, wersjonowanie danych, testowanie scenariuszy rozjazdu |

---

## Zalecenie: 1 → 3, pojazdem jest 2

Wariant 1 daje APK w jeden dzień i **od razu weryfikuje założenie**, czy telefon
jest w ogóle wygodnym narzędziem w wykopie — zanim włoży się w to trzy tygodnie.
Capacitor jest bazą pod wariant 3, więc żaden krok się nie marnuje.

**Czego to rozumowanie nie uwzględniało:** wariant 1 nie da się w ogóle
zrealizować bez HTTPS. Sprawdzenie środowiska (brak certyfikatu, serwer pod
`192.168.x.x`) przestawiło kolejność na **2 → 3**, a wariant 1 przesunęło za
wdrożenie HTTPS. Capacitor i tak był bazą pod jedno i drugie, więc plan
kosztował na tym zero.

Kolejność ma znaczenie także z innego powodu: dopiero praca na budowie pokaże,
czego naprawdę brakuje. Może się okazać, że aparat jest ważniejszy od pełnego
offline — albo odwrotnie.

---

## Co trzeba dołożyć po stronie serwera

Lista rzeczy do zrobienia **zanim** ruszy wariant 2 lub 3.

### 1. Uwierzytelnianie tokenem

Dziś działa sesja w ciasteczku. W WebView ciasteczka bywają kasowane, a klient
natywny potrzebuje czegoś, co przetrwa restart aplikacji.

```
POST /api/token   {login, haslo}  →  {token, wygasa}
Authorization: Bearer <token>
```

Sesja ciasteczkowa zostaje dla przeglądarki — dwa mechanizmy obok siebie,
nie zamiast siebie.

### 2. Paczka synchronizacyjna

```
GET /api/sync/paczka?od_wersji=N
```

Komplet danych roboczych w jednym żądaniu, przyrostowo. Wymaga znacznika wersji
przy rekordach — dziś jest tylko `zmieniono` na `network_object`, reszta tabel
go nie ma.

### 3. Klucz idempotencji przy zapisach ⚠️

Raport wysłany z kolejki offline po odzyskaniu zasięgu **nie może zapisać się
dwa razy**. Klient nadaje własny identyfikator wpisu, serwer odrzuca powtórkę.

To nie jest teoretyczne ryzyko. W etapie 4 dokładnie taki mechanizm zawiódł przy
imporcie: brak klucza naturalnego dał **2442 połączenia zamiast 880**
(patrz [`11-audyt-danych.md`](11-audyt-danych.md)). Synchronizacja offline to ten
sam problem, tylko uruchamiany przez każdy telefon osobno.

### 4. Rozstrzyganie konfliktów

Dwóch monterów bez zasięgu wpisuje inną rzędną tego samego punktu.

**Przyjęta zasada: oba wpisy zostają.** Dziennik wykonawczy i tak jest
dopisywalny — pomiar nigdy nie nadpisuje projektu ani innego pomiaru — więc
konflikt ląduje na liście do rozstrzygnięcia zamiast znikać. Zasada „ostatni
wygrywa" gubiłaby pomiar zrobiony w wykopie, czyli dokładnie tę daną, dla której
całe narzędzie powstało.

Dla **stanu odcinka** jest inaczej: to jedno pole, więc wygrywa zmiana
o późniejszym znaczniku czasu, a pozostałe zostają w historii `zmiana_statusu`.

### 5. HTTPS

Wymagany i tak — przez PWA, service workera i TWA. Dziś aplikacja chodzi po HTTP
(patrz [`07`](07-uwierzytelnianie-i-uzytkownicy.md)).

### 6. Pobranie kafelków obszaru roboczego

Endpoint zwracający paczkę kafelków dla wskazanego arkusza i zakresu przybliżeń,
żeby nie ciągnąć 32 MB PDF-a na telefon.

---

## Czego APK nie powinien robić

**Renderowania PDF-ów.** Kafelki i wycinki zostają na serwerze. PyMuPDF na
Androidzie to droga donikąd, a wycinek profilu jest potrzebny raz na jakiś czas,
nie co minutę — spokojnie może wymagać zasięgu.

**Liczenia niwelacji od nowa.** Serwis `spadek_ciagu.py` już to robi i jest
pokryty testami. Klient ma pokazywać wynik, nie powielać wzoru — dwie
implementacje tego samego rachunku to gwarancja, że kiedyś dadzą różne liczby.

---

## Szacunek nakładu

| Krok | Nakład | Zależy od |
|---|---|---|
| HTTPS + `assetlinks.json` | 0,5 dnia | dostęp do domeny |
| Wariant 1 (TWA, Bubblewrap) | 1 dzień | HTTPS |
| Token + `/api/sync/paczka` | 3–4 dni | — |
| Wariant 2 (Capacitor, aparat, GPS) | 1–2 tygodnie | token |
| Wariant 3 (offline-first + sync) | 3–4 tygodnie | paczka, idempotencja |
| Publikacja w Google Play | 2–3 dni | konto dewelopera, polityka prywatności |

Publikacja w Play nie jest konieczna — APK da się zainstalować wprost na
telefonach ekipy. Dla narzędzia jednej budowy to zwykle prostsze.

---

## Co już jest gotowe

Etapy 3–5 zostawiły więcej fundamentu, niż wynika z ich opisu:

- **PWA z service workerem** — wariant 1 jest praktycznie na wyciągnięcie ręki,
- **interfejs działa na telefonie** — tryb terenowy z etapu 3 (większe pola
  dotykowe, czcionki pod rękawice),
- **georeferencja** — bez niej GPS na mapie nie miałby sensu,
- **kody QR** — skan studni już prowadzi do karty obiektu,
- **API JSON** — większość widoków ma odpowiednik maszynowy,
- **role z monterem** — model uprawnień gotowy na to, że w aplikacji siedzi cała
  ekipa, a nie tylko kierownik.
