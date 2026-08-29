/* Praca bez zasiegu.
 *
 * Na budowie zasieg bywa zaden, a rzedna dna jest potrzebna wlasnie tam -
 * przy wykopie, nie w biurze. Ten skrypt sprawia, ze raz otwarte strony
 * otwieraja sie ponownie takze bez sieci.
 *
 * Dwie strategie, bo dwa rodzaje tresci:
 *
 *   statyki (CSS, JS, czcionki, ikony)  -> najpierw cache
 *        Nie zmieniaja sie miedzy wdrozeniami, a ich pobieranie to wiekszosc
 *        czasu ladowania strony przy slabym zasiegu.
 *
 *   dane (HTML, /api/...)               -> najpierw siec, cache jako zapas
 *        Rzedne musza byc aktualne. Ale gdy sieci nie ma, lepiej pokazac
 *        wczorajsza wartosc z wyraznym ostrzezeniem niz nie pokazac nic.
 *
 * Czego NIE zapisujemy: zadan POST (zapis pomiaru, logowanie) i kafelkow mapy.
 * Pomiar zapisany "na niby" bylby gorszy niz blad - brygadzista mysli, ze
 * dane sa w bazie, a ich tam nie ma. Kafelki z kolei zajelyby setki megabajtow.
 */

const WERSJA = "budowa-v1";
const CACHE_STATYKI = WERSJA + "-statyki";
const CACHE_DANE = WERSJA + "-dane";

// Minimum, zeby aplikacja w ogole sie otworzyla bez sieci.
const SZKIELET = [
  "/static/css/app.css",
  "/static/css/motywy.css",
  "/static/js/app.js",
  "/static/vendor/bootstrap/css/bootstrap.min.css",
  "/static/vendor/bootstrap/js/bootstrap.bundle.min.js",
  "/static/vendor/bootstrap-icons/font/bootstrap-icons.min.css",
  "/static/vendor/jquery/jquery.min.js",
  "/offline",
];

self.addEventListener("install", (zdarzenie) => {
  zdarzenie.waitUntil(
    caches.open(CACHE_STATYKI)
      // addAll przerywa sie w calosci przy jednym bledzie - stad pojedynczo.
      .then((cache) => Promise.allSettled(SZKIELET.map((u) => cache.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (zdarzenie) => {
  zdarzenie.waitUntil(
    caches.keys()
      .then((klucze) => Promise.all(
        klucze.filter((k) => !k.startsWith(WERSJA)).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

function jestStatyka(url) {
  return url.pathname.startsWith("/static/");
}

function pomijamy(url, zadanie) {
  return (
    zadanie.method !== "GET" ||
    url.pathname.startsWith("/mapa/kafelek/") ||   // setki megabajtow
    url.pathname.startsWith("/login") ||
    url.pathname.startsWith("/logout")
  );
}

self.addEventListener("fetch", (zdarzenie) => {
  const zadanie = zdarzenie.request;
  const url = new URL(zadanie.url);

  if (url.origin !== self.location.origin || pomijamy(url, zadanie)) return;

  if (jestStatyka(url)) {
    zdarzenie.respondWith(
      caches.match(zadanie).then((zapisana) =>
        zapisana ||
        fetch(zadanie).then((odpowiedz) => {
          if (odpowiedz.ok) {
            const kopia = odpowiedz.clone();
            caches.open(CACHE_STATYKI).then((c) => c.put(zadanie, kopia));
          }
          return odpowiedz;
        })
      )
    );
    return;
  }

  zdarzenie.respondWith(
    fetch(zadanie)
      .then((odpowiedz) => {
        if (odpowiedz.ok) {
          const kopia = odpowiedz.clone();
          caches.open(CACHE_DANE).then((c) => c.put(zadanie, kopia));
        }
        return odpowiedz;
      })
      .catch(() =>
        caches.match(zadanie).then((zapisana) => {
          if (zapisana) {
            // Naglowek mowi stronie, ze oglada dane sprzed chwili bez sieci.
            const naglowki = new Headers(zapisana.headers);
            naglowki.set("X-Z-Cache", "1");
            return zapisana.blob().then((tresc) =>
              new Response(tresc, { status: 200, headers: naglowki }));
          }
          return caches.match("/offline");
        })
      )
  );
});
