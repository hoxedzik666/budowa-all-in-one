#!/usr/bin/env bash
# Instalacja narzedzia na telefonie (Termux).
#
# Uruchamiac Z KATALOGU PROJEKTU:  ./termux/instaluj.sh
#
# Skrypt jest napisany tak, zeby dalo sie go puscic drugi raz: kazdy krok
# sprawdza, czy nie jest juz zrobiony. Nic nie kasuje - ani bazy, ani .env.
set -euo pipefail

cd "$(dirname "$0")/.."
PROJEKT="$PWD"

Z_PDF=0
for arg in "$@"; do
    case "$arg" in
        --z-pdf) Z_PDF=1 ;;
        -h|--help)
            echo "Uzycie: ./termux/instaluj.sh [--z-pdf]"
            echo "  --z-pdf   sprobuj doinstalowac PyMuPDF (mapa i wycinki PDF)."
            echo "            Zwykle sie nie uda - patrz docs/project-docs/16-termux.md."
            exit 0 ;;
        *) echo "Nieznany argument: $arg" >&2; exit 1 ;;
    esac
done

echo "=== 1/5  paczki Termuxa ==="
# python-pillow bierzemy jako gotowa paczke: kompilacja Pillow ze zrodel na
# telefonie trwa kilkanascie minut i lubi sie wywrocic na brakujacym naglowku.
pkg install -y python python-pillow clang libjpeg-turbo libpng freetype git

echo
echo "=== 2/5  biblioteki Pythona ==="
pip install --upgrade pip
pip install -r requirements-termux.txt

if [ "$Z_PDF" = "1" ]; then
    echo
    echo "  probuje PyMuPDF (moze sie nie udac - to nie jest blad instalacji)"
    if pip install pymupdf; then
        echo "  PyMuPDF wszedl. Mapa i wycinki PDF beda dzialac."
    else
        echo "  PyMuPDF nie wszedl - tak to zwykle konczy sie na Androidzie."
        echo "  Aplikacja bedzie dzialac bez mapy i wycinkow PDF."
    fi
fi

echo
echo "=== 3/5  plik .env ==="
if [ -f .env ]; then
    echo "  .env juz jest - nie ruszam"
else
    # SECRET_KEY musi przetrwac restart serwera, inaczej po kazdym uruchomieniu
    # wszyscy sa wylogowani. Losujemy raz i zapisujemy.
    KLUCZ=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env <<EOF
# Wygenerowane przez termux/instaluj.sh
FLASK_APP=wsgi.py
FLASK_ENV=production
SECRET_KEY=${KLUCZ}
DATABASE_URL=sqlite:///${PROJEKT}/data/budowa.sqlite3
REMEMBER_COOKIE_DAYS=14
EOF
    echo "  utworzony (baza: data/budowa.sqlite3)"
fi

echo
echo "=== 4/5  baza ==="
mkdir -p data/exports data/zdjecia
set -a; . ./.env; set +a
python -m flask init-db

echo
echo "=== 5/5  konto ==="
# `lista-kont` przy pustej bazie nie wypisuje nic - stad liczenie linii.
LICZBA=$(python -m flask lista-kont | grep -c . || true)
if [ "${LICZBA:-0}" -eq 0 ]; then
    # Haslo wypisuje sie raz na ekranie i dopisuje do .env; w bazie zostaje skrot.
    python -m flask utworz-admina
else
    echo "  konta juz sa (${LICZBA}) - nie zakladam nowego"
    echo "  haslo mozna zmienic: python -m flask zmien-haslo <login>"
fi

echo
echo "======================================================================"
echo " Gotowe."
echo
echo " Uruchomienie:      ./termux/uruchom.sh"
echo " Potem w Chrome:    http://127.0.0.1:8000"
echo
echo " Baza jest pusta - dane z dokumentacji projektowej przenosi sie"
echo " z komputera: tam 'flask zrzut-sqlite', a powstaly plik kopiuje sie"
echo " tutaj jako data/budowa.sqlite3."
echo " Opis krok po kroku: docs/project-docs/16-termux.md"
echo "======================================================================"
