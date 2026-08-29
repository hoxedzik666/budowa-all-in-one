"""Testy regresyjne interfejsu.

Powod powstania: Tailwind emituje wlasne utility o nazwach, ktorych uzywa
Bootstrap. Najgrozniejsze bylo `.collapse { visibility: collapse }` - przez nie
nawigacja i rozwijane sekcje byly NIEWIDOCZNE, mimo ze Bootstrap poprawnie
ustawial im `display`. Objawialo sie to jako "tresc znika zaraz po rozwinieciu"
oraz brak menu na szerokim ekranie.

Poprawka to prefiks `tw-` w konfiguracji Tailwinda. Te testy pilnuja, zeby
nikt go przypadkiem nie usunal.
"""
import re
from pathlib import Path

import pytest

KATALOG = Path(__file__).resolve().parent.parent
BASE_HTML = KATALOG / "app" / "templates" / "layouts" / "base.html"
TAILWIND = KATALOG / "app" / "static" / "vendor" / "tailwind" / "tailwind.play.js"


def test_tailwind_ma_prefiks():
    """Bez prefiksu utility Tailwinda nadpisuja komponenty Bootstrapa."""
    tresc = BASE_HTML.read_text(encoding="utf-8")
    assert 'prefix: "tw-"' in tresc, (
        "Konfiguracja Tailwinda musi miec prefiks - inaczej `.collapse`, `.table`, "
        "`.container`, `.border` i `.shadow` zderzaja sie z Bootstrapem."
    )


@pytest.mark.skipif(not TAILWIND.exists(), reason="brak zwendorowanego Tailwinda")
def test_tailwind_faktycznie_definiuje_kolizyjne_utility():
    """Dokumentuje przyczyne bledu - gdyby ktos chcial usunac prefiks."""
    tresc = TAILWIND.read_text(encoding="utf-8", errors="ignore")
    assert 'visibility:"collapse"' in tresc.replace(" ", "")


def test_nawigacja_nie_jest_ukryta_przez_klase_collapse(klient):
    """Menu musi byc w HTML i miec klasy Bootstrapa, nie Tailwinda."""
    html = klient.get("/").get_data(as_text=True)
    assert 'class="collapse navbar-collapse" id="menu"' in html
    assert 'data-bs-target="#menu"' in html


def test_wlasny_css_nie_nadpisuje_widocznosci_collapse():
    """Zaden nasz arkusz nie moze ruszac `visibility` dla `.collapse`."""
    for nazwa in ("app.css", "motywy.css"):
        plik = KATALOG / "app" / "static" / "css" / nazwa
        tresc = plik.read_text(encoding="utf-8")
        for regula in re.findall(r"\.collapse[^{]*\{[^}]*\}", tresc):
            assert "visibility" not in regula, f"{nazwa}: {regula}"


# ------------------------------------------------------------------ motywy


def test_motyw_ustawia_sie_przed_pierwszym_malowaniem():
    """Skrypt motywu musi byc w <head>, inaczej strona mignie na bialo."""
    tresc = BASE_HTML.read_text(encoding="utf-8")
    head = tresc[: tresc.index("</head>")]
    assert "data-bs-theme" in head
    assert "localStorage.getItem" in head


def test_arkusz_motywow_ma_wszystkie_warianty():
    css = (KATALOG / "app" / "static" / "css" / "motywy.css").read_text(encoding="utf-8")
    for selektor in ('[data-motyw="slonce"]', '[data-motyw="warsztat"]', '[data-teren="1"]'):
        assert selektor in css, f"brak motywu {selektor}"


def test_przelacznik_motywu_jest_na_stronie(klient):
    html = klient.get("/").get_data(as_text=True)
    assert 'data-motyw="slonce"' in html
    assert 'data-motyw="warsztat"' in html
    assert 'id="przelacznik-teren"' in html


# ------------------------------------------------------- rozwijane sekcje


def test_importy_maja_poprawna_strukture_akordeonu(klient):
    """Blad zglaszany jako "uwagi znikaja od razu po rozwinieciu"."""
    html = klient.get("/importy").get_data(as_text=True)
    if "accordion-collapse" not in html:
        pytest.skip("brak importow w bazie")
    assert "accordion-collapse collapse" in html
    assert 'data-bs-toggle="collapse"' in html


def test_pulpit_pokazuje_podglad_planu(klient):
    html = klient.get("/").get_data(as_text=True)
    if "Plan sytuacyjny" not in html:
        pytest.skip("brak pliku planow sytuacyjnych")
    assert "/mapa/strona/" in html
