/* Funkcje telefonu: GPS, aparat, skaner kodow QR.
 *
 * Ten plik laduje sie na kazdej stronie, ale robi cokolwiek **tylko wewnatrz
 * aplikacji na Androida**. W przegladarce `window.Capacitor` nie istnieje,
 * wiec przyciski natywne w ogole sie nie pokazuja - dzieki temu te same
 * szablony Flaska obsluguja jedno i drugie, bez rozgalezien po stronie serwera.
 *
 * Calosc: docs/project-docs/15-aplikacja-android.md
 */
(function ($) {
  "use strict";

  var wtyczki = (window.Capacitor && window.Capacitor.Plugins) || null;
  var wAplikacji = Boolean(wtyczki);

  window.telefon = { dostepny: wAplikacji };

  if (!wAplikacji) {
    // Poza aplikacja nie ma czego wlaczac. Elementy oznaczone `data-tylko-apk`
    // zostaja ukryte przez CSS.
    return;
  }

  document.documentElement.setAttribute("data-apk", "1");

  function blad(tresc) {
    /* Komunikaty ida przez ten sam pasek, co reszta aplikacji - brygadzista
     * nie ma rozrozniac, czy blad przyszedl z serwera, czy z telefonu. */
    var pasek = $('<div class="alert alert-warning alert-dismissible fade show" role="alert">')
      .append($("<span>").text(tresc))
      .append('<button type="button" class="btn-close" data-bs-dismiss="alert"></button>');
    $("main").prepend(pasek);
  }

  // ------------------------------------------------------------------ GPS

  /* Zwraca pozycje albo rzuca wyjatkiem z powodem po polsku. */
  window.telefon.pozycja = async function () {
    var uprawnienie = await wtyczki.Geolocation.checkPermissions();
    if (uprawnienie.location !== "granted") {
      uprawnienie = await wtyczki.Geolocation.requestPermissions();
    }
    if (uprawnienie.location !== "granted") {
      throw new Error("Bez zgody na dostęp do lokalizacji nie pokażę, gdzie stoisz.");
    }

    var odczyt = await wtyczki.Geolocation.getCurrentPosition({
      enableHighAccuracy: true,
      // Na otwartym terenie ustalenie pozycji potrafi zajac kilkanascie sekund.
      timeout: 20000,
      // Odczyt sprzed minuty jest bezuzyteczny, gdy przeszedles 200 m.
      maximumAge: 10000
    });
    return {
      lat: odczyt.coords.latitude,
      lon: odczyt.coords.longitude,
      dokladnosc: odczyt.coords.accuracy
    };
  };

  // --------------------------------------------------------------- aparat

  /* Zdjecie jako Blob gotowy do wyslania. */
  window.telefon.zdjecie = async function () {
    var wynik = await wtyczki.Camera.getPhoto({
      quality: 80,
      allowEditing: false,
      resultType: "uri",
      source: "CAMERA",
      // Serwer i tak zmniejsza do 1600 px, ale wysylanie 12 megapikseli przez
      // zasieg na budowie trwaloby minute.
      width: 1600,
      correctOrientation: true
    });
    var odpowiedz = await fetch(wynik.webPath);
    return {
      plik: await odpowiedz.blob(),
      nazwa: "zdjecie." + (wynik.format || "jpg")
    };
  };

  async function wyslijZdjecie(blob, nazwa, powiazanie, opis) {
    var dane = new FormData();
    dane.append("zdjecie", blob, nazwa);
    if (opis) dane.append("opis", opis);
    Object.keys(powiazanie).forEach(function (klucz) {
      if (powiazanie[klucz]) dane.append(klucz, powiazanie[klucz]);
    });

    var odpowiedz = await fetch("/api/zdjecia", { method: "POST", body: dane });
    var wynik = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(wynik.blad || "Nie udało się wysłać zdjęcia.");
    return wynik.zdjecie;
  }

  /* Przycisk [data-zdjecie] robi zdjecie i przypina je tam, gdzie wskazuje
   * `data-dotyczy` / `data-pomiar` / `data-raport`. */
  $(document).on("click", "[data-zdjecie]", async function () {
    var przycisk = $(this);
    var stara = przycisk.html();
    try {
      var zdjecie = await window.telefon.zdjecie();
      przycisk.prop("disabled", true)
        .html('<span class="spinner-border spinner-border-sm"></span> Wysyłam…');

      /* `data-dotyczy-z` wskazuje pole formularza, z ktorego wziac odcinek -
       * dzieki temu przycisk przy raporcie dziennym przypina zdjecie do tego,
       * co czlowiek wlasnie wpisal, zamiast wymagac drugiego wpisania. */
      var zrodlo = przycisk.data("dotyczy-z");
      var dotyczy = zrodlo ? $.trim($(zrodlo).val() || "") : przycisk.data("dotyczy");
      if (!dotyczy && !przycisk.data("pomiar") && !przycisk.data("raport")) {
        throw new Error("Najpierw wpisz odcinek — inaczej za miesiąc nikt nie "
                        + "odgadnie, czego to zdjęcie dotyczy.");
      }

      var zapisane = await wyslijZdjecie(zdjecie.plik, zdjecie.nazwa, {
        dotyczy: dotyczy,
        pomiar_id: przycisk.data("pomiar"),
        raport_id: przycisk.data("raport")
      }, przycisk.data("opis"));

      przycisk.prop("disabled", false).html(stara);

      var galeria = $(przycisk.data("zdjecie"));
      if (galeria.length) {
        galeria.removeClass("d-none").append(
          $("<a>").attr({ href: zapisane.adres, target: "_blank", rel: "noopener" })
            .addClass("me-1")
            .append($("<img>").attr("src", zapisane.adres_miniatury)
              .addClass("rounded border")
              .css({ height: "4rem", width: "auto" })));
      }
    } catch (wyjatek) {
      przycisk.prop("disabled", false).html(stara);
      // Anulowanie aparatu to nie blad - czlowiek sie rozmyslil.
      if (!/cancel/i.test(wyjatek.message || "")) blad(wyjatek.message);
    }
  });

  // ---------------------------------------------------------- skaner kodow

  window.telefon.skanuj = async function () {
    var skaner = wtyczki.BarcodeScanner;
    var zgoda = await skaner.requestPermissions();
    if (zgoda.camera !== "granted" && zgoda.camera !== "limited") {
      throw new Error("Bez zgody na aparat nie zeskanuję kodu.");
    }

    /* Modul skanowania na czesci telefonow doinstalowuje sie z Google Play
     * przy pierwszym uzyciu. Bez tego sprawdzenia skan po prostu nic nie robi. */
    if (skaner.isGoogleBarcodeScannerModuleAvailable) {
      var stan = await skaner.isGoogleBarcodeScannerModuleAvailable();
      if (!stan.available) {
        await skaner.installGoogleBarcodeScannerModule();
        throw new Error("Pobieram moduł skanera — spróbuj ponownie za chwilę.");
      }
    }

    var wynik = await skaner.scan({ formats: ["QR_CODE"] });
    if (!wynik.barcodes || !wynik.barcodes.length) return null;
    return wynik.barcodes[0].rawValue;
  };

  $(document).on("click", "[data-skanuj]", async function () {
    try {
      var tresc = await window.telefon.skanuj();
      if (!tresc) return;

      /* Kod ze studni zawiera pelny adres karty obiektu. Gdyby ktos zeskanowal
       * kod z innego serwera, nie chcemy tam wyjsc - bierzemy sama sciezke. */
      var kod = tresc;
      try {
        var adres = new URL(tresc);
        kod = adres.searchParams.get("q") || adres.pathname;
      } catch (e) { /* nie adres, tylko sam kod obiektu */ }

      window.location.href = "/szukaj?q=" + encodeURIComponent(kod);
    } catch (wyjatek) {
      if (!/cancel/i.test(wyjatek.message || "")) blad(wyjatek.message);
    }
  });

  // ------------------------------------------------------- adres serwera

  $(document).on("click", "[data-zmien-serwer]", function () {
    if (!wtyczki.KonfiguracjaSerwera) return;
    if (window.confirm("Zapomnieć adres serwera i wrócić do ekranu wyboru?")) {
      wtyczki.KonfiguracjaSerwera.zapomnij();
    }
  });
})(jQuery);
