#!/usr/bin/env bash
# Zbuduj APK. Uruchamiane w kontenerze przez `docker compose run --rm build`.
#
# Skrypt jest napisany tak, zeby dalo sie go uruchamiac wielokrotnie: kazdy krok
# sprawdza, czy nie jest juz zrobiony. Dzieki temu ponowne budowanie po zmianie
# jednego pliku nie pobiera od nowa calego Androida.
set -euo pipefail

cd /projekt

echo "=== 1/4  zaleznosci npm ==="
if [ ! -d node_modules ] || [ package.json -nt node_modules ]; then
    npm install --no-audit --no-fund
else
    echo "  node_modules aktualne - pomijam"
fi

echo
echo "=== 2/4  projekt Androida ==="
if [ ! -d android ]; then
    echo "  tworze od zera"
    npx cap add android
else
    echo "  projekt istnieje - synchronizuje"
fi

# Nasze wlasne pliki natywne nadpisuja te wygenerowane przez Capacitora.
# Kolejnosc ma znaczenie: `cap add` tworzy szablonowa MainActivity, ktora
# musimy podmienic na wersje czytajaca adres serwera z ustawien telefonu.
if [ -d natywne ]; then
    echo "  wgrywam wlasne pliki natywne"
    cp -rv natywne/. android/
fi

npx cap sync android

echo
echo "=== 3/4  gradle ==="
cd android
chmod +x gradlew
./gradlew --no-daemon assembleDebug

echo
echo "=== 4/4  wynik ==="
cd /projekt
mkdir -p wyjscie

ZRODLO=android/app/build/outputs/apk/debug/app-debug.apk
if [ ! -f "$ZRODLO" ]; then
    echo "BLAD: gradle nie wyprodukowal $ZRODLO" >&2
    exit 1
fi

WERSJA=$(node -p "require('./package.json').version")
CEL="wyjscie/budowa-${WERSJA}-debug.apk"
cp "$ZRODLO" "$CEL"

echo
echo "  $CEL"
ls -lh "$CEL" | awk '{print "  rozmiar: " $5}'
echo
echo "  --- co siedzi w tym pliku ---"
aapt dump badging "$CEL" | grep -E "^package|^application-label|uses-permission|sdkVersion" | sed 's/^/  /'
echo
echo "  --- podpis ---"
apksigner verify --print-certs "$CEL" 2>/dev/null | grep -E "Signer #1 (certificate DN|.*digest)" | sed 's/^/  /' \
    || echo "  (apksigner nie potwierdzil podpisu - sprawdz recznie)"
echo
echo "Gotowe. Plik przegraj na telefon i zainstaluj."
echo "Telefon musi miec wlaczona instalacje z nieznanych zrodel."
