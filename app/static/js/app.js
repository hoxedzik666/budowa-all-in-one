/* Warstwa interakcji - jQuery. API zwraca JSON, tu tylko prezentacja. */
(function ($) {
  "use strict";

  // Formatowanie liczb po polsku (przecinek dziesietny).
  window.pl = function (v, miejsca) {
    if (v === null || v === undefined || v === "") return "—";
    return Number(v).toFixed(miejsca === undefined ? 2 : miejsca).replace(".", ",");
  };

  // Filtrowanie tabel bez przeladowania strony.
  $(document).on("input", "[data-filtr-tabeli]", function () {
    var fraza = $(this).val().toLowerCase().trim();
    var cel = $($(this).data("filtr-tabeli"));
    var widoczne = 0;
    cel.find("tbody tr").each(function () {
      var pasuje = $(this).text().toLowerCase().indexOf(fraza) !== -1;
      $(this).toggle(pasuje);
      if (pasuje) widoczne++;
    });
    $("[data-licznik-wierszy]").text(widoczne);
  });

  // Kopiowanie rzednej jednym kliknieciem - przydaje sie przy przepisywaniu do dziennika.
  $(document).on("click", "[data-kopiuj]", function () {
    var wartosc = $(this).data("kopiuj");
    navigator.clipboard.writeText(String(wartosc));
    var $t = $(this);
    var stara = $t.html();
    $t.html('<i class="bi bi-check2"></i>');
    setTimeout(function () { $t.html(stara); }, 900);
  });

  // Wycinek z oryginalnego PDF-a. Konwersja jest kosztowna, wiec rusza dopiero
  // po klinieciu - i tylko raz, potem obrazek jest juz w przegladarce.
  $(document).on("click", "[data-wycinek]", function () {
    var przycisk = $(this);
    var pojemnik = $("#wycinek-" + przycisk.data("wycinek"));
    var obraz = pojemnik.find("img");

    if (obraz.attr("src")) {
      pojemnik.toggleClass("d-none");
      return;
    }

    var stara = przycisk.html();
    przycisk.prop("disabled", true)
            .html('<span class="spinner-border spinner-border-sm"></span> Wycinam…');
    obraz.on("load", function () {
      przycisk.prop("disabled", false).html('<i class="bi bi-eye-slash"></i> Ukryj oryginał');
      pojemnik.removeClass("d-none");
    }).on("error", function () {
      przycisk.prop("disabled", false).html(stara);
      pojemnik.removeClass("d-none").find("div").last().html(
        '<div class="alert alert-warning py-2 px-3 small mb-0">' +
        "Tego fragmentu nie da się wyciąć — odcinek nie ma zapisanego położenia na arkuszu." +
        "</div>");
    }).attr("src", przycisk.data("adres"));
  });

  // Podsumowanie wykonania odcinka. Najwazniejsza liczba nie jest tu "czy
  // rzedne sie zgadzaja", tylko czy woda poplynie - czyli rzeczywisty spadek
  // i jego kierunek.
  function opiszWykonanie(dane) {
    if (!dane.pomiarow) {
      return '<span class="text-body-secondary">Brak pomiarów wykonawczych. ' +
        "Po ułożeniu rury wpisz rzędną z niwelatora — program policzy odchyłkę.</span>";
    }
    var czesci = ["<strong>" + dane.pomiarow + "</strong> pomiarów"];
    if (dane.poza_tolerancja) {
      czesci.push('<span class="badge text-bg-warning">' + dane.poza_tolerancja +
                  " poza tolerancją</span>");
    } else {
      czesci.push('<span class="badge text-bg-success">wszystko w tolerancji</span>');
    }
    if (dane.najwieksza_odchylka_m !== null) {
      czesci.push("największa odchyłka " +
                  window.pl(dane.najwieksza_odchylka_m, 3) + " m");
    }
    if (dane.spadek) {
      var s = dane.spadek;
      var opis = "spadek wykonany <strong>" + window.pl(s.spadek_promile, 1) +
                 "‰</strong> na " + window.pl(s.dlugosc_m, 1) + " m";
      if (dane.spadek_projektowy_promile !== null) {
        opis += " (projekt " + window.pl(dane.spadek_projektowy_promile, 1) + "‰)";
      }
      if (s.poprawny_kierunek === false) {
        opis += ' <span class="badge text-bg-danger">woda płynie pod górę</span>';
      }
      czesci.push(opis);
    }
    return czesci.join(" · ");
  }

  $(function () {
    $('[data-bs-toggle="tooltip"]').each(function () {
      new bootstrap.Tooltip(this);
    });

    $("[data-wykonanie]").each(function () {
      var blok = $(this);
      $.getJSON(blok.data("wykonanie"))
        .done(function (dane) { blok.find(".podsumowanie-wykonania").html(opiszWykonanie(dane)); })
        .fail(function () {
          blok.find(".podsumowanie-wykonania")
              .html('<span class="text-body-secondary">Nie udało się pobrać wykonania.</span>');
        });
    });
  });
})(jQuery);

/* ------------------------------------------------------------------ MOTYWY
 * Dwie niezalezne osie zapamietywane w localStorage:
 *   motyw   - domyslny | slonce | warsztat  (kolorystyka)
 *   schemat - auto | light | dark           (tylko dla motywu domyslnego)
 *   teren   - "1" | "0"                     (rozmiary elementow)
 * Pierwsze ustawienie robi maly skrypt w <head>, zeby strona nie mignela.
 */
(function ($) {
  "use strict";

  function pobierz(klucz, domyslnie) {
    try { return localStorage.getItem(klucz) || domyslnie; } catch (e) { return domyslnie; }
  }
  function zapisz(klucz, wartosc) {
    try { localStorage.setItem(klucz, wartosc); } catch (e) { /* brak localStorage */ }
  }

  function zastosuj() {
    var motyw = pobierz("motyw", "domyslny");
    var schemat = pobierz("schemat", "auto");
    var teren = pobierz("teren", "0") === "1";
    var el = document.documentElement;

    var efektywny = schemat;
    if (efektywny === "auto") {
      efektywny = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    // Motywy o wlasnej kolorystyce narzucaja swoj schemat.
    if (motyw === "warsztat") efektywny = "dark";
    if (motyw === "slonce") efektywny = "light";

    el.setAttribute("data-bs-theme", efektywny);
    el.setAttribute("data-motyw", motyw);
    if (teren) { el.setAttribute("data-teren", "1"); } else { el.removeAttribute("data-teren"); }

    $("[data-motyw]").removeClass("aktywny").filter("[data-motyw='" + motyw + "']").addClass("aktywny");
    $("[data-schemat]").removeClass("aktywny").filter("[data-schemat='" + schemat + "']").addClass("aktywny");
    $("#przelacznik-teren").prop("checked", teren);
    // Motyw z wlasna kolorystyka ignoruje wybor schematu - pokazmy to wprost.
    $("[data-schemat]").prop("disabled", motyw !== "domyslny")
      .toggleClass("disabled", motyw !== "domyslny");
  }

  $(document).on("click", ".przelacznik-motywu [data-motyw]", function (e) {
    e.preventDefault();
    zapisz("motyw", $(this).data("motyw"));
    zastosuj();
  });
  $(document).on("click", ".przelacznik-motywu [data-schemat]", function (e) {
    e.preventDefault();
    zapisz("schemat", $(this).data("schemat"));
    zastosuj();
  });
  $(document).on("change", "#przelacznik-teren", function () {
    zapisz("teren", this.checked ? "1" : "0");
    zastosuj();
  });

  // Zmiana ustawienia systemowego przestawia motyw tylko w trybie "auto".
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (pobierz("schemat", "auto") === "auto") zastosuj();
    });
  }

  $(zastosuj);
})(jQuery);
