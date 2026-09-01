#!/usr/bin/env bash
# Uruchomienie serwera przy starcie telefonu - dla dodatku Termux:Boot.
#
# Instalacja (raz):
#   1. Zainstaluj Termux:Boot (F-Droid), uruchom go raz i zamknij.
#   2. mkdir -p ~/.termux/boot
#   3. ln -s ~/budowa-all-in-one/termux/autostart.sh ~/.termux/boot/budowa
#
# Od tej pory serwer wstaje sam po wlaczeniu telefonu i APK ma sie z czym
# polaczyc bez wchodzenia do Termuxa.
#
# Czy to potrzebne: nie. Bez tego wystarczy przed wyjazdem otworzyc Termuxa
# i puscic ./termux/uruchom.sh - jeden raz na dzien pracy.
set -euo pipefail

# Termux:Boot uruchamia skrypty bez ekranu, wiec rygiel czuwania jest tu
# konieczny - inaczej Android uspi serwer po kilkudziesieciu sekundach.
termux-wake-lock 2>/dev/null || true

KATALOG="${BUDOWA_KATALOG:-$HOME/budowa-all-in-one}"
cd "$KATALOG"

mkdir -p data
# Log zostaje na telefonie: gdy serwer nie wstal, to jedyne miejsce, w ktorym
# widac dlaczego (przy starcie z Boota nie ma na czym wypisac bledu).
exec ./termux/uruchom.sh >> data/autostart.log 2>&1
