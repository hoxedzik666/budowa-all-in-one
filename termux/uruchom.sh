#!/usr/bin/env bash
# Uruchomienie serwera na telefonie.
#
#   ./termux/uruchom.sh           serwer tylko dla tego telefonu (127.0.0.1)
#   ./termux/uruchom.sh --siec    serwer widoczny dla calej sieci Wi-Fi
#
# Zatrzymanie: Ctrl+C.
set -euo pipefail

cd "$(dirname "$0")/.."

ADRES="127.0.0.1"
PORT="${WEB_PORT:-8000}"
OTWORZ=0

for arg in "$@"; do
    case "$arg" in
        --siec|--sieć) ADRES="0.0.0.0" ;;
        --otworz|--otwórz) OTWORZ=1 ;;
        -h|--help)
            echo "Uzycie: ./termux/uruchom.sh [--siec] [--otworz]"
            echo "  bez opcji  serwer slucha tylko na 127.0.0.1 (ten telefon)"
            echo "  --siec     serwer slucha na wszystkich adresach - reszta"
            echo "             brygady moze wejsc przez Wi-Fi"
            echo "  --otworz   otworz strone w przegladarce po starcie"
            exit 0 ;;
        *) echo "Nieznany argument: $arg" >&2; exit 1 ;;
    esac
done

if [ ! -f .env ]; then
    echo "Brak pliku .env - uruchom najpierw ./termux/instaluj.sh" >&2
    exit 1
fi
set -a; . ./.env; set +a

# Android usypia procesy w tle, a wtedy serwer przestaje odpowiadac w polowie
# zapisu pomiaru. Rygiel trzyma telefon przy zyciu; zdejmujemy go przy wyjsciu,
# zeby nie zjadal baterii po zamknieciu.
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    trap 'termux-wake-unlock >/dev/null 2>&1 || true' EXIT
fi

echo "======================================================================"
if [ "$ADRES" = "0.0.0.0" ]; then
    IP=$(ip -4 addr show 2>/dev/null | awk '/inet 192\.168\.|inet 10\./ {print $2}' \
         | cut -d/ -f1 | head -n1)
    echo " Serwer widoczny w sieci Wi-Fi."
    echo "   na tym telefonie:  http://127.0.0.1:${PORT}"
    [ -n "${IP:-}" ] && echo "   z innych urzadzen: http://${IP}:${PORT}"
    echo
    echo " UWAGA: haslo leci wtedy po sieci otwartym tekstem. W sieci budowy"
    echo " to swiadomy kompromis - w obcej sieci lepiej bez --siec."
else
    echo " Serwer tylko dla tego telefonu: http://127.0.0.1:${PORT}"
    echo " (zeby wpuscic reszte brygady: ./termux/uruchom.sh --siec)"
fi
echo "======================================================================"
echo

# Otwarcie przegladarki jest **dodatkiem** - gdy sie nie uda, serwer ma dzialac
# dalej, dlatego kazda proba konczy sie `|| true`, a calosc leci w tle: gunicorn
# nie zdazyl jeszcze wstac, wiec czekamy chwile, zeby Chrome nie trafil w pustke.
if [ "$OTWORZ" = "1" ]; then
    (
        # Podpowloka dziedziczy pulapke EXIT ustawiona wyzej, wiec konczac sie
        # po dwoch sekundach zdjelaby rygiel czuwania **dzialajacemu serwerowi**.
        # Objaw bylby mylacy: serwer chodzi, a po zgaszeniu ekranu przestaje
        # odpowiadac. Dlatego tutaj pulapke kasujemy.
        trap - EXIT
        sleep 2
        if command -v termux-open-url >/dev/null 2>&1; then
            # Pakiet `termux-api` + aplikacja Termux:API. Najczystsza droga.
            termux-open-url "http://127.0.0.1:${PORT}" || true
        elif command -v am >/dev/null 2>&1; then
            # Zapas na telefony bez Termux:API - `am` jest w samym Termuxie.
            am start -a android.intent.action.VIEW \
                -d "http://127.0.0.1:${PORT}" >/dev/null 2>&1 || true
        else
            echo "  (nie mam czym otworzyc przegladarki - wpisz adres recznie)"
        fi
    ) &
fi

# Jeden proces roboczy, kilka watkow: telefon ma malo pamieci, a zadania sa
# krotkie i czekaja glownie na dysk. `--timeout 120` zostawia zapas na wolna
# pamiec flash przy zapisie zdjecia.
exec python -m gunicorn \
    --bind "${ADRES}:${PORT}" \
    --workers 1 --threads 4 \
    --timeout 120 \
    --access-logfile - \
    wsgi:app
