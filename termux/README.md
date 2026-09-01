# Serwer na telefonie (Termux)

Trzy skrypty, które sprawiają, że całe narzędzie działa **na telefonie**, bez
komputera w sieci. Pełny opis z uzasadnieniami:
[`docs/project-docs/16-termux.md`](../docs/project-docs/16-termux.md).

```bash
pkg install git
git clone <adres-repozytorium> ~/budowa-all-in-one
cd ~/budowa-all-in-one
./termux/instaluj.sh        # paczki, biblioteki, .env, baza, konto admina
./termux/uruchom.sh         # serwer na http://127.0.0.1:8000
```

Potem otwórz w Chrome `http://127.0.0.1:8000` — albo wskaż ten sam adres
w aplikacji z `.apk/` (przycisk **Serwer na tym telefonie**).

| Skrypt | Co robi |
|---|---|
| `instaluj.sh` | Instaluje paczki Termuxa i biblioteki Pythona, tworzy `.env` z wylosowanym `SECRET_KEY`, zakłada bazę i konto administratora. Można puszczać wielokrotnie. `--z-pdf` próbuje dołożyć PyMuPDF. |
| `uruchom.sh` | Startuje gunicorna. Domyślnie tylko dla tego telefonu; `--siec` wpuszcza resztę brygady przez Wi-Fi. Trzyma rygiel czuwania, żeby Android nie uśpił serwera. |
| `autostart.sh` | Opcjonalny: uruchomienie przy starcie telefonu przez dodatek Termux:Boot. |

## Dane

Baza po instalacji jest **pusta** — i to wystarczy do niwelatora, zadań
i raportów. Dokumentacji projektowej telefon nie zaimportuje (import PDF wymaga
PyMuPDF, którego na Androidzie nie ma), więc dane przenosi się z komputera:

```bash
# na komputerze, przy działającym docker compose:
docker compose exec web python -m flask zrzut-sqlite
# powstaje data/exports/budowa-telefon.sqlite3 — przegraj go na telefon jako:
#   ~/budowa-all-in-one/data/budowa.sqlite3
```

## Czego na telefonie nie ma

Mapa planów, kafelki i wycinki oryginału PDF — wszystko, co czyta rysunek.
Zamiast błędu pokazują stronę z wyjaśnieniem. Reszta narzędzia działa: szukaj,
karty odcinków, przelicznik rur, niwelator, tyczenie ciągu, materiały, postęp
robót, raporty, zadania, kody QR i zdjęcia.
