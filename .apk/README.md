# Aplikacja na Androida

Powłoka Capacitora dla narzędzia **Budowa All-in-One**. Aplikacja pokazuje tę
samą stronę, co przeglądarka, ale dokłada GPS, aparat i skaner kodów QR.

Opis architektury: [`docs/project-docs/15-aplikacja-android.md`](../docs/project-docs/15-aplikacja-android.md)

---

## Zbudowanie

Na komputerze **nie musi być** ani Javy, ani Node, ani Android SDK — wszystko
siedzi w obrazie Dockera.

```bash
docker compose -f .apk/docker-compose.yml build      # raz, ok. 1,8 GB
docker compose -f .apk/docker-compose.yml run --rm build
```

Gotowy plik: `.apk/wyjscie/budowa-1.0.0-debug.apk`

Pierwsze budowanie ciągnie Gradle i zależności — kilkanaście minut.
Kolejne korzystają z wolumenów i schodzą do około dwóch minut.

---

## Instalacja na telefonie

1. Przegraj plik `.apk` na telefon (kabel, Bluetooth, pendrive).
2. Otwórz go menedżerem plików.
3. Android zapyta o zgodę na instalację z nieznanych źródeł — trzeba ją włączyć
   dla aplikacji, z której instalujesz (menedżera plików albo przeglądarki).
4. Przy pierwszym uruchomieniu wpisz **adres serwera**, np. `192.168.2.121:8000`.
   Protokół i port dopiszą się same.

Aplikacja sprawdza połączenie **przed** zapisaniem adresu, więc od razu wiadomo,
czy serwer odpowiada.

### Zmiana adresu serwera

Menu konta (ikona osoby w prawym górnym rogu) → **Zmień adres serwera**.
Nie trzeba odinstalowywać aplikacji.

---

## Uprawnienia, o które prosi aplikacja

| Uprawnienie | Do czego | Czy konieczne |
|---|---|---|
| Internet, stan sieci | połączenie z serwerem | tak |
| Lokalizacja | „Gdzie jestem" na planie | nie — reszta działa bez niej |
| Aparat | zdjęcia z wykopu, skaner QR | nie |
| Zdjęcia w pamięci | wybór gotowego zdjęcia zamiast robienia nowego | nie |

Aparat i GPS są oznaczone jako **opcjonalne** — tablet bez aparatu ma nadal
pokazywać rzędne i spadki.

---

## Co działa bez zasięgu

Tyle, ile daje service worker aplikacji: **raz otwarte strony otwierają się
ponownie**. Zapisu (pomiar, raport, zdjęcie) bez sieci nie da się wykonać —
program powie o tym wprost, zamiast udawać, że zapisał.

Przed wyjazdem na budowę warto otworzyć karty odcinków, nad którymi będzie się
pracować.

Pełna praca offline z kolejką zmian to osobny etap — opisany w
[`13-android-apk.md`](../docs/project-docs/13-android-apk.md) jako wariant 3.

---

## ⚠️ Podpis: teraz debugowy

APK jest podpisany kluczem debugowym, który generuje się sam. To wystarcza
do instalacji i testów w terenie.

**Przejście na klucz release wymusi odinstalowanie wcześniejszej wersji** —
Android nie zaktualizuje aplikacji podpisanej innym kluczem, a razem
z odinstalowaniem znika zapisany adres serwera. Dlatego klucz release robi się
**raz**, gdy aplikacja się ustabilizuje, i przechowuje poza tym komputerem:
jego utrata oznacza, że nie da się już wydać aktualizacji.

---

## Struktura katalogu

```
Dockerfile              JDK 21 + Node 20 + Android SDK 35
docker-compose.yml      usługa `build`, wolumeny na cache
zbuduj.sh               skrypt budowania (4 kroki, idempotentny)
package.json            wersje Capacitora i wtyczek — PRZYPIĘTE
capacitor.config.json   appId, zgoda na HTTP; BEZ adresu serwera
web/                    ekran konfiguracji adresu (jedyna strona z wnętrza APK)
natywne/                nasze pliki nadpisujące wygenerowane przez Capacitora
  └── app/src/main/
      ├── AndroidManifest.xml          uprawnienia, zgoda na HTTP
      ├── res/xml/network_security_config.xml
      └── java/pl/budowa/allinone/
          ├── MainActivity.java        adres serwera → konfiguracja mostu
          └── KonfiguracjaSerwera.java wtyczka: zapis adresu i restart
android/                generowane przez `npx cap add android` — nie edytować
wyjscie/                gotowe pliki .apk
```

**Pliki w `natywne/` nadpisują te w `android/`** przy każdym budowaniu.
Nigdy nie poprawiaj `android/` bezpośrednio — `npx cap sync` skasuje zmiany.

---

## Częste problemy

**„Nie mogę się połączyć" na ekranie konfiguracji**
Telefon musi być w tej samej sieci Wi-Fi co serwer. Sprawdź adres komendą
`ipconfig` na komputerze z serwerem — szukaj `192.168.`. Zapora Windows potrafi
blokować port 8000 dla połączeń z sieci; trzeba go otworzyć.

**Aplikacja pokazuje ekran konfiguracji przy każdym uruchomieniu**
Adres nie zapisał się w ustawieniach telefonu. Sprawdź, czy klucz w
`web/shell.js` i w `MainActivity.java` to nadal `adres_serwera` — pilnuje tego
test `test_klucz_adresu_jest_ten_sam_po_obu_stronach`.

**Skaner QR nic nie robi**
Moduł skanowania Google doinstalowuje się z Play przy pierwszym użyciu.
Aplikacja o tym mówi i prosi o ponowną próbę za chwilę.

**Budowanie kończy się błędem o wersji Javy albo SDK**
Wersje Capacitora, JDK i SDK muszą do siebie pasować. Obecny zestaw:
Capacitor 7 + JDK 21 + SDK 35. Cofnięcie do Capacitora 6 wymaga JDK 17
i SDK 34 w `Dockerfile`.
