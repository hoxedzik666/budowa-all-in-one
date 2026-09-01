/* Ekran konfiguracji adresu serwera.
 *
 * To jedyna strona ladowana z wnetrza APK. Po zapisaniu adresu aktywnosc
 * natywna (MainActivity) uruchamia sie od nowa i tym razem laduje juz Flaska -
 * z mostem Capacitora, dzieki czemu GPS, aparat i skaner dzialaja na stronach
 * serwera. Szczegoly: docs/project-docs/15-aplikacja-android.md
 */
(function () {
  "use strict";

  var KLUCZ = "adres_serwera";
  /* Serwer uruchomiony w Termuxie na tym samym telefonie. Petla zwrotna nie
   * przechodzi przez siec, wiec dziala tez w trybie samolotowym i bez Wi-Fi. */
  var TEN_TELEFON = "http://127.0.0.1:8000";
  var pole = document.getElementById("adres");
  var przycisk = document.getElementById("polacz");
  var przyciskTenTelefon = document.getElementById("ten-telefon");
  var komunikat = document.getElementById("komunikat");

  function pokaz(tekst, rodzaj) {
    komunikat.textContent = tekst;
    komunikat.className = "komunikat" + (rodzaj ? " " + rodzaj : "");
  }

  /* Ludzie wpisuja "192.168.2.121" albo "192.168.2.121:8000/" - jedno i drugie
   * ma zadzialac. Domyslamy sie protokolu i portu, ucinamy ukosnik na koncu. */
  function uporzadkuj(surowy) {
    var adres = (surowy || "").trim();
    if (!adres) return "";
    if (!/^https?:\/\//i.test(adres)) adres = "http://" + adres;
    adres = adres.replace(/\/+$/, "");
    if (!/:\d+$/.test(adres.replace(/^https?:\/\//i, ""))) adres += ":8000";
    return adres;
  }

  function most() {
    return window.Capacitor && window.Capacitor.Plugins;
  }

  async function wczytajZapisany() {
    var wtyczki = most();
    if (wtyczki && wtyczki.Preferences) {
      var wynik = await wtyczki.Preferences.get({ key: KLUCZ });
      return wynik.value || "";
    }
    try { return localStorage.getItem(KLUCZ) || ""; } catch (e) { return ""; }
  }

  async function zapisz(adres) {
    var wtyczki = most();
    if (wtyczki && wtyczki.Preferences) {
      await wtyczki.Preferences.set({ key: KLUCZ, value: adres });
    }
    /* Zapis rownolegly do localStorage: MainActivity czyta SharedPreferences,
     * ale gdyby wtyczka zawiodla, adres nie przepada. */
    try { localStorage.setItem(KLUCZ, adres); } catch (e) { /* brak miejsca */ }
  }

  /* Zanim wpuscimy kogos w aplikacje, sprawdzamy, czy serwer w ogole odpowiada.
   * Lepiej powiedziec "nie odpowiada" tutaj niz pokazac biala strone. */
  async function sprawdz(adres) {
    var kontroler = new AbortController();
    var stoper = setTimeout(function () { kontroler.abort(); }, 6000);
    try {
      var odpowiedz = await fetch(adres + "/api/zdrowie", {
        signal: kontroler.signal,
        cache: "no-store"
      });
      if (!odpowiedz.ok) {
        return { ok: false, powod: "Serwer odpowiedział błędem " + odpowiedz.status + "." };
      }
      var dane = await odpowiedz.json();
      if (dane && dane.status === "ok") return { ok: true };
      return { ok: false, powod: "Pod tym adresem odpowiada coś innego niż Budowa All-in-One." };
    } catch (blad) {
      if (blad.name === "AbortError") {
        return { ok: false, powod: "Serwer nie odpowiedział w 6 sekund. Sprawdź Wi-Fi i adres." };
      }
      return { ok: false, powod: "Nie mogę się połączyć. Czy telefon jest w tej samej sieci co serwer?" };
    } finally {
      clearTimeout(stoper);
    }
  }

  async function polacz() {
    var adres = uporzadkuj(pole.value);
    if (!adres) {
      pokaz("Wpisz adres serwera.", "blad");
      pole.focus();
      return;
    }
    pole.value = adres;

    przycisk.disabled = true;
    pokaz("Sprawdzam połączenie…", "czekam");

    var wynik = await sprawdz(adres);
    if (!wynik.ok) {
      przycisk.disabled = false;
      pokaz(wynik.powod, "blad");
      return;
    }

    await zapisz(adres);
    pokaz("Połączono. Uruchamiam aplikację…", "ok");

    /* MainActivity nasluchuje na tej zmianie: po zapisaniu adresu przeladowuje
     * WebView juz na serwer. Gdy mostu nie ma (np. podglad w przegladarce),
     * przechodzimy wprost - bez natywnych funkcji, ale dziala. */
    var wtyczki = most();
    if (wtyczki && wtyczki.KonfiguracjaSerwera) {
      await wtyczki.KonfiguracjaSerwera.ustaw({ adres: adres });
    } else {
      window.location.href = adres + "/";
    }
  }

  przycisk.addEventListener("click", polacz);
  pole.addEventListener("keydown", function (zdarzenie) {
    if (zdarzenie.key === "Enter") polacz();
  });

  /* Przycisk tylko wpisuje adres i idzie ta sama droga co reczne wpisanie -
   * lacznie ze sprawdzeniem serwera. Gdy Termux nie jest uruchomiony, czlowiek
   * dowie sie tego tutaj, a nie po bialym ekranie w aplikacji. */
  przyciskTenTelefon.addEventListener("click", function () {
    pole.value = TEN_TELEFON;
    polacz();
  });

  wczytajZapisany().then(function (zapisany) {
    /* Podpowiedz z budowania (DOMYSLNY_SERWER) trafia tu przy generowaniu APK. */
    pole.value = zapisany || pole.getAttribute("placeholder") || "";
    if (zapisany) {
      pokaz("Ten adres był używany ostatnio.", null);
    }
    pole.focus();
  });

  document.getElementById("wersja").textContent =
    "Wskaż adres serwera, żeby zacząć";
})();
