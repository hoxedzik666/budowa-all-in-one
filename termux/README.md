# Serwer na telefonie (Termux)

Całe narzędzie działa **na telefonie**, bez komputera w sieci. Pełny opis
z uzasadnieniami: [`docs/project-docs/16-termux.md`](../docs/project-docs/16-termux.md).

```bash
pkg install git
git clone <adres-repozytorium> ~/budowa-all-in-one
cd ~/budowa-all-in-one
./start.sh
```

To wszystko: pierwszy raz instaluje i zakłada konto, za każdym razem uruchamia
serwer na `http://127.0.0.1:8000` i otwiera stronę. Login i hasło wypisuje
w ramce przy starcie.

Ten sam adres wskazuje się w aplikacji z `.apk/` — przycisk **Serwer na tym
telefonie**.

| Skrypt | Co robi |
|---|---|
| `../start.sh` | Jedno polecenie: doinstalowuje, czego brakuje, startuje serwer, otwiera przeglądarkę. |
| `instaluj.sh` | Paczki Termuxa i biblioteki Pythona, `.env` z wylosowanym `SECRET_KEY`, baza z dokumentacją, konto administratora. Można puszczać wielokrotnie. `--z-pdf` próbuje dołożyć PyMuPDF. |
| `uruchom.sh` | Sam serwer. Domyślnie tylko dla tego telefonu; `--siec` wpuszcza brygadę przez Wi-Fi, `--otworz` otwiera przeglądarkę. Trzyma rygiel czuwania, żeby Android nie uśpił serwera. |
| `autostart.sh` | Opcjonalny: uruchomienie przy starcie telefonu przez dodatek Termux:Boot. |

## Dane

**Są od razu.** W repozytorium leży `data/baza-startowa/budowa.sqlite3` —
odczytana dokumentacja projektowa (649 odcinków, 7 439,5 m sieci), bez kont
i bez raportów. `instaluj.sh` kopiuje ją do `data/budowa.sqlite3`, ale tylko
gdy tej bazy jeszcze nie ma: istniejącej nie nadpisuje.

Żeby mieć na telefonie bazę swojej ekipy (z kontami, raportami i historią):

```bash
# na komputerze, przy działającym docker compose:
docker compose exec web python -m flask zrzut-sqlite
# powstały plik przegraj na telefon jako:
#   ~/budowa-all-in-one/data/budowa.sqlite3
```

## Czego na telefonie nie ma

Mapa planów, kafelki i wycinki oryginału PDF — wszystko, co czyta rysunek,
bo PyMuPDF nie instaluje się na Androidzie. Zamiast błędu pokazują stronę
z wyjaśnieniem. Reszta działa: szukaj, karty odcinków, przelicznik rur,
niwelator, tyczenie ciągu, materiały, postęp robót, raporty, zadania, kody QR
i zdjęcia.
