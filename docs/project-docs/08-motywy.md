# Motywy graficzne

---

## Dostępne motywy

Przełącznik jest w pasku nawigacji (ikona palety). Wybór zapamiętuje się
w przeglądarce i przeżywa odświeżenie.

| Motyw | Do czego |
|---|---|
| **Domyślny** | jasny, ciemny albo wg ustawienia systemu |
| **Wysoki kontrast** | czerń na bieli, grube obramowania, pogrubione liczby — do czytania telefonu w pełnym słońcu na budowie |
| **Nocny warsztat** | ciemne tło z bursztynową kolorystyką zamiast niebieskiej — mniej męczy oczy po zmroku i nie psuje adaptacji wzroku |
| **Tryb terenowy** | większe czcionki, wyższe wiersze, większe pola dotykowe — do obsługi w rękawicach roboczych |

**Tryb terenowy jest niezależny od kolorystyki** — można go włączyć razem
z każdym z pozostałych. To celowe: rozmiar elementów i dobór barw rozwiązują
dwa różne problemy, a rozdzielenie ich daje 6 kombinacji z 4 reguł CSS zamiast
mnożenia wariantów.

---

## Jak to działa

Trzy niezależne atrybuty na elemencie `<html>`:

```html
<html data-bs-theme="light|dark"      <!-- natywny mechanizm Bootstrapa 5.3 -->
      data-motyw="domyslny|slonce|warsztat"
      data-teren="1">                  <!-- obecny tylko gdy włączony -->
```

Stan trzymany w `localStorage`:

| Klucz | Wartości |
|---|---|
| `motyw` | `domyslny` · `slonce` · `warsztat` |
| `schemat` | `auto` · `light` · `dark` (działa tylko dla motywu domyślnego) |
| `teren` | `1` · `0` |

Motywy o własnej kolorystyce narzucają swój schemat: „wysoki kontrast” zawsze
jasny, „nocny warsztat” zawsze ciemny. Menu wygasza wtedy wybór schematu,
żeby nie sugerować, że coś zmieni.

### Brak mignięcia przy wczytywaniu

Krótki skrypt w `<head>` (`layouts/base.html`) ustawia atrybuty **przed
pierwszym malowaniem strony**. Gdyby robił to dopiero `app.js` na końcu `<body>`,
strona mignęłaby na biało przy każdym przejściu w motywie ciemnym.

Skrypt jest opakowany w `try/catch` — w oknie prywatnym `localStorage` potrafi
rzucić wyjątkiem, a to nie może wywalić strony.

Ekran logowania ma własny, uproszczony szkielet (nie dziedziczy z `base.html`),
więc ten sam skrypt jest tam powtórzony.

---

## ⚠️ Tailwind musi mieć prefiks

To nie jest kwestia stylu — bez prefiksu **interfejs się psuje**.

Tailwind emituje własne utility o nazwach, których Bootstrap używa jako nazw
komponentów:

```css
/* Tailwind, plugin `visibility` */
.visible   { visibility: visible }
.invisible { visibility: hidden }
.collapse  { visibility: collapse }   ← ⚠️
```

```css
/* Bootstrap — steruje wyłącznie `display` */
.collapse:not(.show) { display: none }
```

Tailwind Play CDN wstrzykuje swój `<style>` **w czasie działania**, czyli po
`<link>` Bootstrapa. Ta sama specyficzność, późniejsza pozycja w kaskadzie →
wygrywa Tailwind. Każdy element z klasą `collapse` dostaje `visibility: collapse`
i jest **niewidoczny**, choćby Bootstrap poprawnie ustawił mu `display`.

Objawy, które to powodowało:

| Objaw | Mechanizm |
|---|---|
| treść rozwijanej sekcji znika zaraz po rozwinięciu | w trakcie animacji działa klasa `.collapsing` (Tailwind jej nie rusza, treść widać), po zakończeniu klasa zmienia się na `.collapse.show` → `visibility: collapse` → znika |
| brak nawigacji na szerokim ekranie | `.navbar-collapse.collapse` jest niewidoczna mimo `display: flex` |
| nawigacja znika na telefonie | przycisk dodaje `.show`, Bootstrap ustawia `display: block`, ale `visibility: collapse` zostaje |

Kolidują też `.table` (używana w 50 miejscach), `.container`, `.border`,
`.rounded` i `.shadow`.

**Rozwiązanie** — w `layouts/base.html`:

```js
tailwind.config = { prefix: "tw-", corePlugins: { preflight: false } };
```

Od tej pory klasy Tailwinda pisze się `tw-flex`, `tw-gap-2` itd. i nie mogą
zderzyć się z niczym. `preflight: false` zostaje wyłączony, żeby Tailwind nie
resetował stylów bazowych Bootstrapa.

Pilnują tego testy w `tests/test_ui_regresja.py` — sprawdzają obecność prefiksu,
istnienie kolizyjnego utility w bibliotece (żeby udokumentować przyczynę) oraz to,
że własne arkusze nie ruszają `visibility` dla `.collapse`.

---

## Jak dodać kolejny motyw

1. Dopisz blok w `app/static/css/motywy.css`:
   ```css
   [data-motyw="nazwa"] {
     --bs-body-bg: …;
     --bs-body-color: …;
     --bs-primary: …;
     --bs-border-color: …;
   }
   [data-motyw="nazwa"] body { background: … !important; }
   [data-motyw="nazwa"] .kafelek { background: …; border-color: …; }
   ```
   Najwięcej daje przestawienie **zmiennych CSS Bootstrapa** — komponenty
   podchwycą je same.

2. Dodaj pozycję do listy `motywy` w
   `app/templates/partials/przelacznik_motywu.html`.

3. Jeśli motyw ma narzucać schemat jasny albo ciemny, dopisz go w dwóch
   miejscach: w skrypcie w `<head>` (`base.html`) i w funkcji `zastosuj()`
   w `app/static/js/app.js`.

4. Dopisz selektor do `test_arkusz_motywow_ma_wszystkie_warianty`.

---

## Uwagi

- Rysunek profilu (SVG) ma w motywie „nocny warsztat” wymuszone jasne tło —
  cienkie linie na ciemnym są nieczytelne.
- Wydruk korzysta ze stylów motywu domyślnego jasnego; przed drukowaniem warto
  go przełączyć.
- Motyw zapisuje się **w przeglądarce, nie na koncie** — każde urządzenie może
  mieć własne ustawienie, co jest sensowne: telefon na budowie i monitor w biurze
  pracują w innych warunkach.
