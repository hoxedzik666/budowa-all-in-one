# Aplikacja na Androida

> Stan: **działa**. APK buduje się jedną komendą, jest podpisany i ma komplet
> uprawnień. Kod w [`.apk/`](../../.apk/).

---

## Rewizja planu z dokumentu 13

Dokument [`13`](13-android-apk.md) zalecał kolejność **TWA → offline-first**.
Sprawdzenie środowiska tę kolejność unieważniło:

```
HTTPS                   nigdzie
SESSION_COOKIE_SECURE   nie ustawione
serwer                  http://192.168.x.x:8000  (LAN, bez domeny)
```

**TWA wymaga HTTPS i Digital Asset Links pod publiczną domeną.** Bez tego nie
przechodzi weryfikacji, a stawianie domeny z certyfikatem dla serwera stojącego
w kontenerze na budowie to osobny projekt.

Capacitor takiego wymogu nie ma. Dlatego poszedł pierwszy — a TWA wraca do gry
dopiero razem z HTTPS. Reszta dokumentu 13 zostaje w mocy, zwłaszcza to, że
**APK jest klientem, a nie kopią aplikacji**.

---

## Architektura: jedna aplikacja Flask, dwa sposoby wyświetlania

To jedyna nieoczywista część całego rozwiązania.

Capacitor wstrzykuje most do funkcji natywnych **wyłącznie na origin ustawiony
jako `server.url`** — widać to w `Bridge.setAllowedOriginRules()`, które dodaje
tam właśnie adres z konfiguracji. Gdyby aplikacja ładowała lokalną stronę
powitalną, a potem przechodziła na serwer Flaska, most przestałby istnieć
i żadna funkcja telefonu nie byłaby wywoływalna ze stron aplikacji.

Adres serwera nie może być jednak wbity przy budowaniu: przy DHCP każda zmiana
IP oznaczałaby nowy APK dla całej ekipy.

Rozwiązanie łączy jedno z drugim:

```
MainActivity.onCreate
   │
   ├─ czyta adres z SharedPreferences
   │
   ├─ brak adresu ──► config zostaje pusty
   │                  → Capacitor ładuje capacitor.config.json z zasobów
   │                  → pokazuje lokalny ekran wpisania adresu (web/index.html)
   │                  → KonfiguracjaSerwera.ustaw() zapisuje i restartuje
   │
   └─ adres jest  ──► this.config = CapConfig.Builder().setServerUrl(adres)
                      → super.onCreate() woła load()
                      → most powstaje z adresem serwera
                      → WebView ładuje Flaska Z DZIAŁAJĄCYM GPS-em i aparatem
```

Kluczowy szczegół: `BridgeActivity.onCreate()` kończy się wywołaniem `load()`,
które robi `bridgeBuilder.setConfig(config)`. Pole `config` jest chronione,
więc wystarczy ustawić je **przed** `super.onCreate()`.

### Konsekwencja, która upraszcza całą resztę

**Te same szablony Flaska obsługują przeglądarkę i APK.** Przyciski natywne
zapalają się warunkiem `window.Capacitor !== undefined`:

```css
[data-tylko-apk] { display: none !important; }
html[data-apk="1"] [data-tylko-apk] { display: inline-flex !important; }
```

Zero duplikacji widoków, zero rozgałęzień po stronie serwera. Pilnuje tego
`tests/test_apk.py`.

### ⚠️ Przy aktualizacji Capacitora sprawdź to jako pierwsze

Capacitor nie ma publicznego API do zmiany adresu serwera w locie. `MainActivity`
opiera się na chronionym polu klasy bazowej, więc przy zmianie głównej wersji
biblioteki ten fragment trzeba przejrzeć.

---

## Funkcje telefonu

Cała warstwa po stronie przeglądarki siedzi w
[`app/static/js/telefon.js`](../../app/static/js/telefon.js).

### GPS — „gdzie jestem" na planie

Jedyna funkcja korzystająca wprost z georeferencji z etapu 4. Łańcuch jest
w całości po stronie serwera; telefon podaje tylko dwie liczby i dokładność:

```
GPS (WGS84) ──► PL-2000/5 ──► przekształcenie georeferencji ──► punkt rysunku
        wspolrzedne.py            georef.py
```

`GET /api/mapa/z-gps/<nr>?lat=&lon=&dokladnosc=`

Transformacja przez **`pyproj`** (EPSG:4326 → EPSG:2176). W
[`02-technologie.md`](02-technologie.md) stało, że bibliotekę dokładamy,
„gdyby doszła transformacja między układami" — to był ten moment.
Odwzorowania Gaussa-Krügera nie pisze się ręcznie: błąd w szóstym miejscu po
przecinku daje kilkanaście metrów w terenie i nie widać go inaczej niż przez
porównanie z punktem kontrolnym.

**Sprawdzenie poprawności ma twardy punkt odniesienia.** Wszystkie 151 punktów
osnowy przeliczone odwrotnie lądują w przedziale:

```
szerokość 52,0168 .. 52,0773 N
długość   15,0551 .. 15,1464 E     ← Krosno Odrzańskie
błąd powrotu tam i z powrotem: 1–2 mm
```

Drugi test idzie dalej: bierze reper, którego pozycję na rysunku sami wskazaliśmy,
przelicza go na WGS84 i pyta serwer, gdzie leży. Wraca to samo miejsce
z dokładnością 0,5 pt.

#### Dokładność jest pokazywana zawsze

GPS w telefonie ma 3–10 m. **To znajdzie studnię i nie wytyczy rury.** Ładny
znacznik na mapie kusi, żeby o tym zapomnieć, więc dymek mówi to wprost przy
każdym odczycie, a nie tylko przy błędzie. Wokół znacznika rysuje się koło
niepewności w skali mapy.

Odczyt spoza Polski albo o dokładności gorszej niż 15 m dostaje osobne
ostrzeżenie — najczęściej znaczy to włączoną w telefonie pozycję testową.

### Aparat — zdjęcia z wykopu

Rzędna mówi, że wykop ma 1,73 m. Zdjęcie mówi, że na dnie stoi woda. Przy sporze
o odbiór to zdjęcie jest dowodem.

| | |
|---|---|
| Model | `Zdjecie` — powiązanie z pomiarem, raportem, obiektem albo odcinkiem |
| Pliki | `data/zdjecia/RRRR-MM/` — **poza `data/exports/`** |
| Endpoint | `POST /api/zdjecia` (multipart), `GET /zdjecia/<id>.jpg` |
| Rozmiar | zmniejszane do 1600 px + miniatura 320 px |
| Limit | `MAX_CONTENT_LENGTH` 25 MB |

Katalog ma znaczenie: `exports` to kasowalny cache, który odtworzy się sam.
Zdjęcie z wykopu nie odtworzy się nigdy — wykop zostanie zasypany.

Zdjęcia przechodzą przez `ImageOps.exif_transpose`, bo telefon zapisuje
orientację w EXIF zamiast obracać piksele; bez tego połowa zdjęć leży na boku.

**Przy okazji domknięta luka:** aplikacja nie miała dotąd żadnego limitu
wielkości przesyłanego pliku.

### Skaner QR

`@capacitor-mlkit/barcode-scanning`. Przycisk w pasku wyszukiwarki, widoczny
tylko w APK. Skan naklejki ze studni otwiera kartę obiektu bez wychodzenia do
aparatu systemowego.

Z kodu bierzemy **tylko parametr `q`**, a nie cały adres — zeskanowanie kodu
z innego serwera nie może wyprowadzić aplikacji poza budowę.

Moduł skanowania Google doinstalowuje się z Play przy pierwszym użyciu;
aplikacja o tym mówi zamiast milczeć.

---

## Budowanie

Na komputerze nie ma ani Javy, ani Node, ani Android SDK — i nie musi być.

```bash
docker compose -f .apk/docker-compose.yml build      # raz, 1,8 GB
docker compose -f .apk/docker-compose.yml run --rm build
```

| | |
|---|---|
| Obraz | JDK 21 + Node 20 + Android SDK 35, 1,8 GB |
| Pierwszy build | kilkanaście minut (Gradle + zależności) |
| Kolejne | ~2 minuty, cache w wolumenach |
| Wynik | `.apk/wyjscie/budowa-1.0.0-debug.apk`, **29 MB** |

Rozmiar bierze się głównie z ML Kit do skanowania kodów.

### Pliki natywne

`.apk/natywne/` nadpisuje to, co generuje Capacitor. **Katalogu `.apk/android/`
nie edytuje się nigdy** — `npx cap sync` skasuje zmiany.

### Wersje są przypięte

Capacitor 7 wymaga Node 20+, JDK 21 i SDK 35. Rozjazd którejkolwiek z tych
rzeczy kończy się błędem w połowie budowania, a komunikat rzadko wskazuje
prawdziwą przyczynę. Dlatego `package.json` nie ma `^` ani `~`.

---

## Czego nie zweryfikowano

**Aplikacji nie uruchomiono na telefonie ani w emulatorze.** Potwierdzone jest:
budowanie przechodzi, APK jest podpisany, ma identyfikator `pl.budowa.allinone`,
komplet uprawnień, a obie klasy natywne (`MainActivity`, `KonfiguracjaSerwera`)
i ekran konfiguracji faktycznie znalazły się w paczce.

**Nie jest potwierdzone**, że aplikacja startuje, że most Capacitora działa
z adresem z SharedPreferences i że wtyczki odpowiadają. To pierwsza rzecz do
sprawdzenia po instalacji.

---

## Co dalej

W kolejności wartości, nie trudności:

1. **HTTPS na serwerze** — odblokowuje TWA, zamyka lukę z hasłem lecącym
   otwartym tekstem, jest wymagany przez service workera poza localhostem.
2. **Uwierzytelnianie tokenem** obok sesji ciasteczkowej — ciasteczka w WebView
   bywają kasowane.
3. **Praca offline z kolejką zmian** (wariant 3 z [`13`](13-android-apk.md)).
   Wymaga **klucza idempotencji przy zapisach** — bez tego synchronizacja
   zdubluje dane dokładnie tak, jak zrobił to import w etapie 4
   (2442 połączenia zamiast 880, patrz [`11`](11-audyt-danych.md)).
4. **Klucz release** — gdy aplikacja się ustabilizuje. Zmiana klucza wymusza
   odinstalowanie, więc robi się to raz.
