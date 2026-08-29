# Praca w terenie: dziennik wykonawczy, offline, kody QR

> Trzy rzeczy, które dzieją się przy wykopie, a nie przy biurku.

---

## 1. Dziennik wykonawczy

`/wykonanie` · model `PomiarWykonawczy`

### Zasada: projekt zostaje nietknięty

Cała dotychczasowa baza opisuje **projekt**. Budowa to jednak nie przepisywanie
projektu — rura ląduje o dwa centymetry wyżej, teren okazuje się niższy, studnia
wchodzi na innej rzędnej. Te liczby trzeba gdzieś zapisać, i **nie wolno ich
mieszać z projektem**.

Gdyby pomiar nadpisywał `network_object.rzedna_dna_kanalu`, po tygodniu nikt nie
wiedziałby, co zaprojektowano, a co zbudowano. Dlatego pomiar to osobny rekord,
który tylko **wskazuje** na obiekt albo odcinek, a odchyłkę program liczy
w locie. Pilnuje tego test `test_zapis_pomiaru_nie_rusza_projektu`.

### Co się wpisuje

| Pole | Uwagi |
|---|---|
| Dotyczy | `D155` albo `Wyl101-D155` — to, co jest na rysunku |
| Rodzaj | dno kanału / dno studni / teren |
| Rzędna zmierzona | prosto z niwelatora |
| Odległość | **od pierwszego obiektu w nazwie** — na `Wyl101-D155` metr zerowy jest przy `Wyl101` |
| Data, uwagi | np. „podsypka 15 cm, grunt nawodniony" |

Rzędna projektowa na odcinku liczy się przez interpolację od `rzedna_dna_od` do
`rzedna_dna_do`. To nie jest oczywiste: profile rysuje się od wylotu w górę, więc
`od` bywa **niższym** końcem. Wcześniejsza wersja zgadywała, że początek jest
zawsze wyżej — i odwracała wynik na większości odcinków.

### Tolerancje

| Co | Tolerancja | Dlaczego tyle |
|---|---|---|
| dno kanału | ± 0,02 m | na 3-metrowym przykanaliku błąd 3 cm potrafi odwrócić spadek |
| dno studni | ± 0,03 m | |
| teren | ± 0,05 m | teren nie decyduje o tym, czy woda popłynie |

### Spadek wykonany — liczba, której szuka kierownik

Przy odbiorze nie chodzi o to, „czy rzędne się zgadzają", tylko **czy woda
popłynie**. Rura ułożona o 2 cm za wysoko na obu końcach ma nadal poprawny
spadek. Ułożona o 2 cm za wysoko tylko na końcu — już nie.

Program liczy rzeczywisty spadek z dwóch skrajnych pomiarów i porównuje go
z projektowym, razem z kierunkiem:

```
spadek wykonany 3,9‰ na 20,5 m (projekt 3,0‰)
```

Gdy woda miałaby płynąć pod górę, wychodzi to czerwoną plakietką na karcie
odcinka. Kierunek porównujemy z kierunkiem projektowym tego samego odcinka,
a nie z założeniem „w dół znaczy dodatni" — bo to zależy od tego, jak narysowano
profil.

### Gdzie się wpisuje

- `/wykonanie` — pełny dziennik z filtrem „poza tolerancją",
- **karta odcinka** — przycisk „Wpisz pomiar z niwelatora", tuż pod profilem;
  te same rzędne, które chwilę wcześniej wyliczył kalkulator tyczenia,
- **karta do druku** — puste wiersze na wpisanie ołówkiem w wykopie.

---

## 2. Praca bez zasięgu (PWA)

Narzędzie jest potrzebne przy wykopie, a tam zasięg bywa żaden.

### Jak to działa

`app/static/service-worker.js`, wydawany z `/service-worker.js`

Skrypt **musi** iść z korzenia, nie z `/static/`: przeglądarka ogranicza jego
zasięg do ścieżki, z której go pobrała. Wydany spod `/static/` obsługiwałby
tylko `/static/...` i był bezużyteczny.

Dwie strategie, bo dwa rodzaje treści:

| Treść | Strategia | Dlaczego |
|---|---|---|
| statyki (CSS, JS, ikony) | **najpierw cache** | nie zmieniają się między wdrożeniami, a ich pobieranie to większość czasu ładowania przy słabym zasięgu |
| dane (HTML, `/api/…`) | **najpierw sieć**, cache jako zapas | rzędne muszą być aktualne; gdy sieci nie ma, lepiej wczorajsza wartość z ostrzeżeniem niż nic |

### Czego świadomie NIE zapisujemy

- **żądań POST** (zapis pomiaru, logowanie) — pomiar zapisany „na niby" byłby
  gorszy niż błąd: brygadzista myśli, że dane są w bazie, a ich tam nie ma,
- **kafelków mapy** — zajęłyby setki megabajtów.

### Instalacja na telefonie

Manifest (`app/static/manifest.webmanifest`) pozwala dodać aplikację do ekranu
głównego. Otwiera się wtedy bez paska adresu, jak zwykły program.

⚠️ Service worker wymaga **HTTPS** albo `localhost`. W sieci budowy po HTTP
zarejestruje się tylko na localhost — to kolejny powód, żeby dołożyć HTTPS
(patrz [`07`](07-uwierzytelnianie-i-uzytkownicy.md)).

### Przed wyjazdem na budowę

Otwórz karty odcinków, nad którymi będziesz pracować. To, co raz zobaczysz przy
zasięgu, zostaje w telefonie. Ekran `/offline` mówi to wprost, gdy trafisz na
stronę, której nie ma w pamięci.

Przy braku sieci na górze pojawia się pasek: *„Brak zasięgu. Widzisz dane
zapisane w telefonie przy ostatnim połączeniu."*

---

## 3. Kody QR na studnie

`/qr`

Studnia w terenie nie ma na sobie numeru. Naklejka z kodem zamienia szukanie
w dokumentacji na jedno zeskanowanie — kod prowadzi wprost do karty obiektu
z rzędnymi, spadkiem i wykazem rur.

- filtr po typie i kodzie, do 120 naklejek na arkusz,
- na naklejce: kod QR, kod obiektu, rzędna dna, DN, nazwa zadania,
- **wysoka korekcja błędów** (poziom H) — naklejka na budowie będzie zachlapana
  betonem i zakurzona, a przy tym poziomie da się odczytać kod mimo ubytków,
- wydruk zostawia same naklejki, bez nawigacji i formularza.

Drukować na folii samoprzylepnej.

---

## 4. Karta odcinka do druku

`/odcinek/<od>/<do>/karta`

Jedna kartka A4 do teczki wykonawczej: profil podłużny, rzędne obu końców,
głębokości wykopu, trzy warianty pocięcia rur, tabela na wpisanie pomiarów
i miejsce na podpis.

Puste wiersze zostają zawsze — kartka ma działać także jako notatnik, gdy
w wykopie nie ma zasięgu ani telefonu pod ręką.

Do tego przycisk „Oryginał z profilu": wektorowy wycinek z `Profile Scalone.pdf`
obejmujący dokładnie ten odcinek ([`06`](06-struktura-projektu.md)).

---

## Eksport dla geodety i kierownictwa

| Format | Skąd | Do czego |
|---|---|---|
| GeoJSON | `/mapa/eksport/<nr>.geojson` | QGIS |
| DXF | `/mapa/eksport/<nr>.dxf` | CAD |
| CSV | `/mapa/eksport/<nr>.csv` | tyczenie z tachimetru |
| `.pgw` | `/mapa/eksport/<nr>.pgw` | plik świata do rastra |
| karta A4 | `/odcinek/<od>/<do>/karta` | teczka wykonawcza |
| arkusz QR | `/qr` | naklejki na studnie |

Szczegóły formatów: [`09-konwerter-planow.md`](09-konwerter-planow.md).
