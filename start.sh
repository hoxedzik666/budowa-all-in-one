#!/usr/bin/env bash
# Jedno polecenie, ktore stawia narzedzie na telefonie.
#
#   ./start.sh
#
# Doinstalowuje, czego brakuje, uruchamia serwer i otwiera strone. Mozna
# wywolywac codziennie - drugi raz pomija wszystko, co jest juz zrobione,
# i po prostu startuje serwer.
set -euo pipefail

cd "$(dirname "$0")"

# --- czy to telefon ---------------------------------------------------------
# Termux ustawia TERMUX_VERSION, a swoje PREFIX trzyma w katalogu aplikacji.
# Ten sam warunek ma app/config.py (funkcja `czy_termux`), zeby baza i skrypt
# rozpoznawaly telefon tak samo.
if [ -z "${TERMUX_VERSION:-}" ] && [[ "${PREFIX:-}" != *com.termux* ]]; then
    cat <<'EOF'
To nie jest Termux.

Na komputerze narzedzie stawia sie Dockerem:

    cp .env.example .env
    docker compose up -d --build
    docker compose exec web python -m flask import-wszystko
    docker compose exec web python -m flask utworz-admina

Potem http://localhost:8000
EOF
    exit 1
fi

# --- instalacja, jesli jej jeszcze nie bylo ---------------------------------
# Dwa warunki, bo kazdy z nich potrafi wystapic osobno: .env kasuje sie recznie,
# a biblioteki znikaja po `pkg upgrade`, ktory podmienil wersje Pythona.
if [ ! -f .env ] || ! python -c "import flask" >/dev/null 2>&1; then
    echo "Pierwsze uruchomienie - instaluje. To potrwa kilka minut."
    echo
    ./termux/instaluj.sh
    echo
fi

# --- czym sie zalogowac -----------------------------------------------------
# Haslo administratora zapisuje `flask utworz-admina` przy instalacji. Bez tej
# ramki "strona dziala", ale nie da sie do niej wejsc - a hasla nikt nie pamieta.
set -a; . ./.env; set +a
if [ -n "${ADMIN_LOGIN:-}" ] && [ -n "${ADMIN_HASLO:-}" ]; then
    echo "======================================================================"
    echo " Logowanie:   ${ADMIN_LOGIN}  /  ${ADMIN_HASLO}"
    echo " (haslo lezy w pliku .env; zmiana: python -m flask zmien-haslo ${ADMIN_LOGIN})"
    echo "======================================================================"
    echo
fi

exec ./termux/uruchom.sh --otworz "$@"
