#!/usr/bin/env python3
"""Audyt branzowy odwodnienia DK29 - dowod liczbowy do docs/audyt-branzowy-dk29.md.

Kontrole, ktorych NIE robi app/services/walidacja.py: spadek minimalny, przykrycie
rury, rozstaw studni, wyniesienie wylotu nad dno rowu, spojnosc zestawienia
materialowego, kompletnosc osnowy.

Tylko biblioteka standardowa - zaden Flask, zaden PyMuPDF, zaden openpyxl. Skrypt
jest read-only: niczego nie zapisuje do bazy i nie ustawia flag. Ma sluzyc do
odtworzenia kazdej liczby z raportu, takze na telefonie w Termuxie.

    python3 scripts/audyt_branzowy.py
    python3 scripts/audyt_branzowy.py --sekcja spadki przykrycie
    python3 scripts/audyt_branzowy.py --limit 0        # pelne listy, bez obcinania
"""

from __future__ import annotations

import argparse
import collections
import math
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
BAZA = KORZEN / "data" / "baza-startowa" / "budowa.sqlite3"
XLSX = KORZEN / "docs" / "Materiał.xlsx"
OSNOWA = KORZEN / "docs" / "!!_DK29_osnowa_ok_v1.txt"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# --- progi branzowe -----------------------------------------------------------
# Zadna z tych liczb nie wystepuje w app/ - to wlasnie jest ustalenie audytu.
STREFA_PRZEMARZANIA_M = 0.8      # PN-81/B-03020, Krosno Odrzanskie - strefa I
MIN_PRZYKRYCIE_M = 1.0           # przyjete robocze minimum pod droga
MAX_ROZSTAW_STUDNI_M = {200: 50, 250: 50, 300: 50, 400: 70, 500: 70, 600: 70, 1000: 100}
MIN_WYNIESIENIE_WYLOTU_M = 0.10  # dno wylotu ponad dnem rowu
SPADEK_EKSTREMALNY_PROMILE = 100.0
ODCINEK_KROTKI_M = 1.0
PLASKI_M = 0.005                 # |dh| ponizej tego = odcinek praktycznie plaski

# srednica zewnetrzna wg katalogu PRAGMA; zgodne z app/services/rury.PROFIL_NA_OD
PROFIL_NA_OD = {200: 200, 250: 250, 300: 315, 400: 400, 500: 500, 600: 630, 1000: 1000}


def f(v):
    return None if v is None else float(v)


def naglowek(tytul: str) -> None:
    print()
    print("=" * 78)
    print(tytul)
    print("=" * 78)


def lista(wiersze, limit: int, wciecie: str = "    ") -> None:
    pokaz = wiersze if limit == 0 else wiersze[:limit]
    for w in pokaz:
        print(wciecie + w)
    if limit and len(wiersze) > limit:
        print(f"{wciecie}... oraz {len(wiersze) - limit} dalszych (--limit 0 pokazuje wszystkie)")


# --- wczytanie zrodel ---------------------------------------------------------

def wczytaj_arkusz(zz: zipfile.ZipFile, teksty: list[str], plik: str) -> dict[int, dict]:
    """Arkusz xlsx jako {numer_wiersza: {litera_kolumny: wartosc}}."""
    korzen = ET.fromstring(zz.read(plik))
    wynik: dict[int, dict] = {}
    for wiersz in korzen.iter(NS + "row"):
        dane = {}
        for komorka in wiersz.iter(NS + "c"):
            wartosc_el = komorka.find(NS + "v")
            if wartosc_el is None:
                inline = komorka.find(NS + "is")
                wartosc = "".join(t.text or "" for t in inline.iter(NS + "t")) if inline is not None else None
            elif komorka.get("t") == "s":
                wartosc = teksty[int(wartosc_el.text)]
            else:
                wartosc = wartosc_el.text
            if wartosc not in (None, ""):
                dane[re.match(r"[A-Z]+", komorka.get("r")).group(0)] = wartosc
        if dane:
            wynik[int(wiersz.get("r"))] = dane
    return wynik


def wczytaj_xlsx(sciezka: Path) -> dict[str, dict[int, dict]]:
    zz = zipfile.ZipFile(sciezka)
    teksty = [
        "".join(t.text or "" for t in si.iter(NS + "t"))
        for si in ET.fromstring(zz.read("xl/sharedStrings.xml")).iter(NS + "si")
    ]
    return {
        "studnie": wczytaj_arkusz(zz, teksty, "xl/worksheets/sheet1.xml"),
        "wpusty": wczytaj_arkusz(zz, teksty, "xl/worksheets/sheet2.xml"),
        "wyloty": wczytaj_arkusz(zz, teksty, "xl/worksheets/sheet3.xml"),
        "rury": wczytaj_arkusz(zz, teksty, "xl/worksheets/sheet4.xml"),
    }


def liczba(tekst):
    if tekst in (None, ""):
        return None
    try:
        return float(str(tekst).replace(",", "."))
    except ValueError:
        return None


def bez_sss(kod: str) -> str:
    """S.S.S. to artefakt nakladajacych sie napisow - patrz sonnet-think-output/02."""
    return re.sub(r"^S\.S\.S\.", "", str(kod)).strip()


def odcinki(baza: sqlite3.Connection):
    return baza.execute(
        """SELECT s.id, a.kod AS kod_od, b.kod AS kod_do, a.typ AS typ_od, b.typ AS typ_do,
                  s.dlugosc_m, s.dn_mm, s.spadek_promile, s.rzedna_dna_od, s.rzedna_dna_do,
                  s.podejrzany, p.branza, p.oznaczenie
           FROM segment s
           JOIN network_object a ON a.id = s.obiekt_od_id
           JOIN network_object b ON b.id = s.obiekt_do_id
           JOIN profile p ON p.id = s.profil_id
           ORDER BY s.id"""
    ).fetchall()


# --- sekcje -------------------------------------------------------------------

def sekcja_spadki(baza, ark, limit):
    naglowek("SPADKI - spadek minimalny, przeciwspadek, wartosci ekstremalne")
    ponizej_min, plaskie, ekstremalne = [], [], []
    for r in odcinki(baza):
        dlugosc, dn = f(r["dlugosc_m"]), r["dn_mm"]
        rz_od, rz_do = f(r["rzedna_dna_od"]), f(r["rzedna_dna_do"])
        if None in (dlugosc, rz_od, rz_do) or dlugosc == 0:
            continue
        rzeczywisty = abs(rz_od - rz_do) / dlugosc * 1000
        para = f"{r['kod_od']}-{r['kod_do']}"
        if abs(rz_od - rz_do) < PLASKI_M:
            plaskie.append(f"{para:<20} L={dlugosc:7.2f} m  dh={abs(rz_od-rz_do)*1000:.0f} mm  rz {rz_od} = {rz_do}")
        if dn and rzeczywisty < 1000.0 / dn:
            ponizej_min.append(
                f"{para:<20} DN{dn:<5d} L={dlugosc:7.2f} m  i={rzeczywisty:6.2f}‰  (i_min = 1/DN = {1000.0/dn:.2f}‰)"
            )
        if rzeczywisty > SPADEK_EKSTREMALNY_PROMILE:
            ekstremalne.append(
                f"{para:<20} DN{str(dn or '?'):<5s} L={dlugosc:7.2f} m  i={rzeczywisty:9.1f}‰  rz {rz_od} -> {rz_do}"
            )

    print(f"\n  Odcinki ponizej reguly praktycznej i_min = 1/DN: {len(ponizej_min)}")
    print("  (kryterium normowe PN-EN 752 to predkosc samooczyszczania - danych o przeplywach brak)")
    lista(sorted(ponizej_min, key=lambda s: float(re.search(r"i=\s*([\d.]+)", s).group(1))), limit)

    print(f"\n  Odcinki praktycznie plaskie (|dh| < {PLASKI_M*1000:.0f} mm): {len(plaskie)}")
    lista(plaskie, limit)

    print(f"\n  Odcinki o spadku > {SPADEK_EKSTREMALNY_PROMILE:.0f}‰: {len(ekstremalne)}")
    lista(sorted(ekstremalne, key=lambda s: -float(re.search(r"i=\s*([\d.]+)", s).group(1))), limit)


def sekcja_przykrycie(baza, ark, limit):
    naglowek("PRZYKRYCIE RURY - strefa przemarzania i minimum pod droga")
    print(f"  przykrycie = rzedna terenu proj. - rzedna dna kanalu - OD (srednica ZEWNETRZNA)")
    print(f"  strefa przemarzania dla Krosna Odrzanskiego: {STREFA_PRZEMARZANIA_M:.1f} m (PN-81/B-03020)")
    plytkie, wszystkich, ponizej_przemarzania = [], 0, 0
    for r in baza.execute(
        """SELECT kod, typ, rzedna_terenu_proj, rzedna_dna_kanalu, dn_mm
           FROM network_object WHERE typ IN ('STUDNIA','WEZEL_KT','OSADNIK','SEPARATOR')"""
    ):
        teren, dno, dn = f(r["rzedna_terenu_proj"]), f(r["rzedna_dna_kanalu"]), r["dn_mm"]
        if None in (teren, dno) or not dn:
            continue
        wszystkich += 1
        przykrycie = teren - dno - PROFIL_NA_OD.get(dn, dn) / 1000.0
        if przykrycie < MIN_PRZYKRYCIE_M:
            ponizej_przemarzania += przykrycie < STREFA_PRZEMARZANIA_M
            znacznik = "  <-- ponizej strefy przemarzania" if przykrycie < STREFA_PRZEMARZANIA_M else ""
            plytkie.append(
                f"{r['kod']:<10} {r['typ']:<10} przykrycie {przykrycie:5.2f} m "
                f"(teren {teren}, dno {dno}, DN{dn}/OD{PROFIL_NA_OD.get(dn, dn)}){znacznik}"
            )
    print(f"\n  Wezlow z przykryciem < {MIN_PRZYKRYCIE_M:.2f} m: {len(plytkie)} z {wszystkich}")
    print(f"  z tego ponizej strefy przemarzania {STREFA_PRZEMARZANIA_M:.1f} m: {ponizej_przemarzania}")
    lista(sorted(plytkie, key=lambda s: float(re.search(r"przykrycie\s+([-\d.]+)", s).group(1))), limit)

    # niezalezne potwierdzenie prosto z arkusza, z pominieciem bazy i parsera PDF
    print("\n  Kontrola niezalezna wprost z Materiał.xlsx / Studnie (RTp - RD1 - D1):")
    kontrola = []
    for dane in ark["studnie"].values():
        kod = dane.get("B")
        rtp, rd1, d1 = liczba(dane.get("E")), liczba(dane.get("J")), liczba(dane.get("I"))
        if not kod or None in (rtp, rd1, d1):
            continue
        p = rtp - rd1 - d1 / 1000.0
        if p < MIN_PRZYKRYCIE_M:
            kontrola.append(f"{bez_sss(kod):<10} przykrycie {p:5.2f} m  (RTp {rtp}, RD1 {rd1}, D1 {d1:.0f})")
    print(f"  Wezlow z przykryciem < {MIN_PRZYKRYCIE_M:.2f} m wg arkusza: {len(kontrola)}")
    lista(sorted(kontrola, key=lambda s: float(re.search(r"przykrycie\s+([-\d.]+)", s).group(1))), limit)


def sekcja_rozstaw(baza, ark, limit):
    naglowek("ROZSTAW STUDNI - odleglosc miedzy wezlami rewizyjnymi")
    print("  limit przyjety: DN<=300 -> 50 m, DN 400-600 -> 70 m, DN>600 -> 100 m")
    print("  (app/services/walidacja.py MAX_DLUGOSC_M = 300 m - tego nie wylapie)")
    przekroczenia, wszystkich = [], 0
    for r in odcinki(baza):
        if r["typ_od"] != "STUDNIA" or r["typ_do"] != "STUDNIA":
            continue
        wszystkich += 1
        dlugosc, dn = f(r["dlugosc_m"]), r["dn_mm"]
        if dlugosc is None:
            continue
        limit_m = MAX_ROZSTAW_STUDNI_M.get(dn, 50)
        if dlugosc > limit_m:
            przekroczenia.append(
                f"{r['kod_od']}-{r['kod_do']:<12} L={dlugosc:7.2f} m  DN{str(dn or '?'):<5s} limit {limit_m} m"
            )
    print(f"\n  Odcinkow studnia-studnia: {wszystkich};  przekraczajacych limit: {len(przekroczenia)}")
    lista(sorted(przekroczenia, key=lambda s: -float(re.search(r"L=\s*([\d.]+)", s).group(1))), limit)


def sekcja_wyloty(baza, ark, limit):
    naglowek("WYLOTY - wyniesienie dna wylotu nad dno rowu")
    print("  zrodlo: Materiał.xlsx / Wyloty, kolumny 'Rz.d.' (E) oraz 'Rz. Dna rowu/zbiornika' (G)")
    rozklad = collections.Counter()
    niskie, ujemne = [], []
    razem = 0
    for dane in ark["wyloty"].values():
        kod = dane.get("B")
        if not kod or not bez_sss(kod).startswith("Wyl"):
            continue
        rzedna, row = liczba(dane.get("E")), liczba(dane.get("G"))
        if None in (rzedna, row):
            continue
        razem += 1
        # rzedne podane z dokladnoscia 1 cm - bez zaokraglenia 80.86-80.76 daje
        # 0.0999999... i wylot wpada do sasiedniego przedzialu
        h = round(rzedna - row, 3)
        opis = f"{bez_sss(kod):<10} dno wylotu {rzedna:7.2f}  dno rowu {row:7.2f}  wyniesienie {h:+.2f} m"
        if h < -0.001:
            ujemne.append(opis)
            rozklad["ujemne (wylot PONIZEJ dna rowu)"] += 1
        elif h < 0.005:
            niskie.append(opis)
            rozklad["0,00 m (rowno z dnem rowu)"] += 1
        elif h < MIN_WYNIESIENIE_WYLOTU_M:
            niskie.append(opis)
            rozklad[f"0,00-{MIN_WYNIESIENIE_WYLOTU_M:.2f} m"] += 1
        elif h < 0.20:
            rozklad["0,10-0,20 m"] += 1
        elif h < 0.50:
            rozklad["0,20-0,50 m"] += 1
        else:
            rozklad["> 0,50 m"] += 1
    print(f"\n  Wylotow z kompletem rzednych: {razem}")
    for klucz in ("ujemne (wylot PONIZEJ dna rowu)", "0,00 m (rowno z dnem rowu)",
                  f"0,00-{MIN_WYNIESIENIE_WYLOTU_M:.2f} m", "0,10-0,20 m", "0,20-0,50 m", "> 0,50 m"):
        print(f"    {klucz:<38} {rozklad[klucz]:4d}")
    print(f"\n  Ponizej {MIN_WYNIESIENIE_WYLOTU_M:.2f} m (lacznie {len(ujemne) + len(niskie)}):")
    lista(ujemne + niskie, limit)


def sekcja_odczyt(baza, ark, limit):
    naglowek("ODCZYT DOKUMENTACJI - odcinki niewykonalne i niespojne")
    krotkie, rozjazd = [], []
    oflagowanych = 0
    for r in odcinki(baza):
        if r["podejrzany"]:
            oflagowanych += 1
        dlugosc = f(r["dlugosc_m"])
        rz_od, rz_do, rys = f(r["rzedna_dna_od"]), f(r["rzedna_dna_do"]), f(r["spadek_promile"])
        para = f"{r['kod_od']}-{r['kod_do']}"
        if dlugosc is not None and dlugosc < ODCINEK_KROTKI_M:
            if dlugosc and None not in (rz_od, rz_do):
                policzony = f"{abs(rz_od - rz_do) / dlugosc * 1000:9.1f}‰"
            else:
                policzony = f"{'brak':>10}"
            krotkie.append(
                f"{para:<20} L={dlugosc:5.2f} m  i_policzony={policzony}  profil {r['oznaczenie']}"
                + ("  [podejrzany]" if r["podejrzany"] else "")
            )
        if None in (dlugosc, rz_od, rz_do, rys) or not dlugosc:
            continue
        policzony = abs(rz_od - rz_do) / dlugosc * 1000
        if abs(policzony - rys) > max(1.0, 0.15 * rys):
            rozjazd.append(
                f"{para:<20} L={dlugosc:7.2f} m  z rysunku {rys:7.1f}‰  z rzednych {policzony:9.1f}‰  "
                f"rz {rz_od} -> {rz_do}  profil {r['oznaczenie']}"
            )
    print(f"\n  Odcinkow krotszych niz {ODCINEK_KROTKI_M:.0f} m: {len(krotkie)}")
    print(f"  (app/services/walidacja.py MIN_DLUGOSC_M = 0.05 m - przepuszcza je wszystkie)")
    lista(sorted(krotkie, key=lambda s: float(re.search(r"L=\s*([\d.]+)", s).group(1))), limit)

    print(f"\n  Rozjazd spadku rysunek <-> rzedne, prog max(1‰, 15%): {len(rozjazd)}")
    lista(sorted(rozjazd, key=lambda s: -float(re.search(r"z rzednych\s+([\d.]+)", s).group(1))), limit)

    print(f"\n  Odcinkow z flaga 'podejrzany' w bazie: {oflagowanych} z 649")


def sekcja_topologia(baza, ark, limit):
    naglowek("TOPOLOGIA - spojnosc sieci i obiekty specjalne")
    sasiedzi = collections.defaultdict(set)
    for kod_a, kod_b in baza.execute(
        """SELECT a.kod, b.kod FROM segment s
           JOIN network_object a ON a.id = s.obiekt_od_id
           JOIN network_object b ON b.id = s.obiekt_do_id"""
    ):
        sasiedzi[kod_a].add(kod_b)
        sasiedzi[kod_b].add(kod_a)

    def skladowa(start):
        stos, zebrane = [start], set()
        while stos:
            wierzcholek = stos.pop()
            if wierzcholek in zebrane:
                continue
            zebrane.add(wierzcholek)
            stos.extend(sasiedzi[wierzcholek] - zebrane)
        return zebrane

    typy = dict(baza.execute("SELECT kod, typ FROM network_object"))
    odwiedzone, skladowe = set(), []
    for wierzcholek in sasiedzi:
        if wierzcholek in odwiedzone:
            continue
        s = skladowa(wierzcholek)
        odwiedzone |= s
        skladowe.append(s)
    bez_wylotu = [s for s in skladowe if not any(typy.get(k) == "WYLOT" for k in s)]
    wylotow = sum(1 for t in typy.values() if t == "WYLOT")
    print(f"\n  Skladowych spojnych: {len(skladowe)}  |  wylotow w sieci: {wylotow}")
    print("  UWAGA: duza liczba skladowych NIE jest bledem - odwodnienie drogowe to wiele")
    print("  krotkich zlewni, kazda z wlasnym wylotem do rowu.")
    print(f"\n  Skladowe BEZ wylotu (brak odbiornika): {len(bez_wylotu)}")
    for s in bez_wylotu:
        print(f"    {len(s):3d} obiektow: {', '.join(sorted(s)[:16])}")

    # graf z arkusza Wpusty (kolumna M 'Odbiornik') kontra odcinki z rysunku
    pary_bazy = {
        frozenset((a, b))
        for a, b in baza.execute(
            """SELECT a.kod, b.kod FROM segment s
               JOIN network_object a ON a.id = s.obiekt_od_id
               JOIN network_object b ON b.id = s.obiekt_do_id"""
        )
    }
    kody = {k for (k,) in baza.execute("SELECT kod FROM network_object")}
    brak_odcinka, brak_obiektu, par = [], [], 0
    for dane in ark["wpusty"].values():
        zrodlo, odbiornik = dane.get("B"), dane.get("M")
        if not zrodlo or not odbiornik or liczba(dane.get("C")) is None:
            continue  # brak RTp => wiersz naglowkowy albo legenda, nie wpust
        zrodlo, odbiornik = bez_sss(zrodlo), bez_sss(odbiornik)
        par += 1
        if odbiornik not in kody:
            brak_obiektu.append(f"{zrodlo} -> {odbiornik} (odbiornik nieznany bazie)")
        elif frozenset((zrodlo, odbiornik)) not in pary_bazy:
            brak_odcinka.append(f"{zrodlo} -> {odbiornik}")
    print(f"\n  Par wpust->odbiornik w arkuszu Wpusty: {par}")
    print(f"  Bez odpowiadajacego odcinka w bazie: {len(brak_odcinka)}")
    lista(brak_odcinka, limit)
    if brak_obiektu:
        print(f"  Odbiornikow nieznanych bazie: {len(brak_obiektu)}")
        lista(brak_obiektu, limit)

    print("\n  Obiekty z arkusza Studnie, ktorych brak w bazie:")
    brakujace = []
    for dane in ark["studnie"].values():
        kod, opis = dane.get("B"), dane.get("D") or ""
        if not kod or kod in ("PZ", "Legenda:"):
            continue
        if liczba(dane.get("E")) is None:
            continue
        if bez_sss(kod) not in kody:
            brakujace.append(f"{bez_sss(kod):<10} {opis[:60]}")
    lista(brakujace, limit) if brakujace else print("    (brak)")

    for kod in ("KT15", "D139"):
        wiersz = baza.execute(
            "SELECT id, kod, typ, rzedna_dna_kanalu, opis FROM network_object WHERE kod = ?", (kod,)
        ).fetchone()
        if wiersz:
            print(f"    {wiersz['kod']:<6} id={wiersz['id']:<5} {wiersz['typ']:<10} "
                  f"rz.dna={wiersz['rzedna_dna_kanalu']}  {(wiersz['opis'] or '')[:40]}")
    print("    ^ sonnet-think-output/02 deklaruje 'KT15=D139' jako jeden obiekt z aliasem")


def sekcja_braki(baza, ark, limit):
    naglowek("KOMPLETNOSC - czego w bazie nie ma")
    razem_odc = baza.execute("SELECT count(*) FROM segment").fetchone()[0]
    razem_ob = baza.execute("SELECT count(*) FROM network_object").fetchone()[0]
    print(f"\n  ODCINKI ({razem_odc}):")
    for kolumna in ("dlugosc_m", "dn_mm", "material", "spadek_promile"):
        n = baza.execute(f"SELECT count(*) FROM segment WHERE {kolumna} IS NOT NULL").fetchone()[0]
        print(f"    {kolumna:<18} wypelnione {n:5d}  ({100*n/razem_odc:5.1f} %)")
    bez_dn = baza.execute("SELECT count(*), round(sum(dlugosc_m),1) FROM segment WHERE dn_mm IS NULL").fetchone()
    calosc = baza.execute("SELECT round(sum(dlugosc_m),1) FROM segment").fetchone()[0]
    print(f"    bez srednicy: {bez_dn[0]} odcinkow = {bez_dn[1]} m z {calosc} m "
          f"({100*float(bez_dn[1])/float(calosc):.0f} % dlugosci sieci)")
    komplet = baza.execute(
        "SELECT count(*) FROM segment WHERE dlugosc_m IS NOT NULL AND dn_mm IS NOT NULL AND spadek_promile IS NOT NULL"
    ).fetchone()[0]
    print(f"    komplet (L + DN + spadek): {komplet} z {razem_odc}")

    print(f"\n  OBIEKTY ({razem_ob}):")
    for kolumna in ("rzedna_dna_kanalu", "rzedna_dna_studni", "dn_mm", "srednica_studni_mm",
                    "material", "x", "y"):
        n = baza.execute(f"SELECT count(*) FROM network_object WHERE {kolumna} IS NOT NULL").fetchone()[0]
        print(f"    {kolumna:<20} wypelnione {n:5d}  ({100*n/razem_ob:5.1f} %)")

    print("\n  KLASA SN - jest w arkuszu, nie ma jej w bazie:")
    # filtr po RTp odsiewa legende i wiersz naglowkowy - liczymy same wezly
    sn_studnie = collections.Counter(
        (d.get("V") or "(brak)").strip() for d in ark["studnie"].values()
        if d.get("B") and liczba(d.get("E")) is not None
    )
    sn_wpusty = collections.Counter(
        (d.get("R") or "(brak)").strip() for d in ark["wpusty"].values()
        if d.get("B") and liczba(d.get("C")) is not None
    )
    print(f"    Studnie, kolumna V: {dict(sn_studnie)}")
    print(f"    Wpusty,  kolumna R: {dict(sn_wpusty)}")
    print(f"    Obiektow z materialem w bazie: "
          f"{baza.execute('SELECT count(*) FROM network_object WHERE material IS NOT NULL').fetchone()[0]}")

    print("\n  KANAL TLOCZNY (branza KT):")
    kt = baza.execute(
        """SELECT count(*) n, round(sum(s.dlugosc_m),2) dl,
                  sum(CASE WHEN s.dn_mm IS NULL THEN 1 ELSE 0 END) bez_dn,
                  sum(CASE WHEN s.material IS NULL THEN 1 ELSE 0 END) bez_mat
           FROM segment s JOIN profile p ON p.id = s.profil_id WHERE p.branza = 'KT'"""
    ).fetchone()
    print(f"    odcinkow {kt['n']}, dlugosc {kt['dl']} m, bez DN {kt['bez_dn']}, bez materialu {kt['bez_mat']}")

    print("\n  GEOREFERENCJA:")
    for tabela in ("plan_location", "plan_georef", "plan_anchor", "pomiar_wykonawczy"):
        print(f"    {tabela:<20} {baza.execute(f'SELECT count(*) FROM {tabela}').fetchone()[0]} wierszy")


def sekcja_material(baza, ark, limit):
    naglowek("ZESTAWIENIE MATERIALOWE - spojnosc Materiał.xlsx z siecia")
    suma = baza.execute("SELECT sum(ilosc_projekt_m) FROM material_item").fetchone()[0]
    rurowe = baza.execute("SELECT sum(ilosc_projekt_m) FROM material_item WHERE dn_od_mm IS NOT NULL").fetchone()[0]
    siec = baza.execute("SELECT round(sum(dlugosc_m),1) FROM segment").fetchone()[0]
    print(f"\n  Suma kolumny ilosc_projekt_m w bazie:            {float(suma):9.1f} m")
    print(f"  z tego pozycje rurowe (dn_od_mm ustalone):       {float(rurowe):9.1f} m")
    print(f"  po odjeciu duplikatu wariantu /3 i /6:           {float(rurowe)/2:9.1f} m")
    print(f"  dlugosc sieci wg profili:                        {float(siec):9.1f} m")
    print("  Arkusz podaje te sama ilosc projektowa dwa razy - raz dla rur 3 m, raz dla 6 m.")
    print("  Kazde zestawienie sumujace te kolumne jest podwojone.")

    duplikaty = collections.defaultdict(list)
    for r in baza.execute(
        "SELECT opis_pozycji, dn_od_mm, klasa_sn, dlugosc_sztuki_m, ilosc_projekt_m FROM material_item "
        "WHERE dn_od_mm IS NOT NULL"
    ):
        duplikaty[(r["dn_od_mm"], r["klasa_sn"])].append((r["dlugosc_sztuki_m"], r["ilosc_projekt_m"]))
    pary_te_same = [
        f"OD{dn} {sn or '?':<5} warianty {[str(w[0]) for w in warianty]} -> ilosc projektowa {[str(w[1]) for w in warianty]}"
        for (dn, sn), warianty in sorted(duplikaty.items())
        if len(warianty) > 1 and len({str(w[1]) for w in warianty}) == 1
    ]
    print(f"\n  Pozycji, gdzie /3 i /6 maja identyczna ilosc projektowa: {len(pary_te_same)}")
    lista(pary_te_same, limit)

    print("\n  Pozycje bez rozpoznanej srednicy (nie da sie powiazac z odcinkiem):")
    bez_dn = [
        f"id {r['id']:<3} {r['opis_pozycji'][:58]:<58} ilosc {r['ilosc_projekt_m']}"
        for r in baza.execute(
            "SELECT id, opis_pozycji, ilosc_projekt_m FROM material_item WHERE dn_od_mm IS NULL ORDER BY id"
        )
    ]
    print(f"  Razem: {len(bez_dn)}")
    lista(bez_dn, limit)

    print("\n  Zestawienie dlugosci wg srednicy: profile PDF kontra arkusz")
    pdf = dict(baza.execute("SELECT dn_mm, round(sum(dlugosc_m),1) FROM segment WHERE dn_mm IS NOT NULL GROUP BY 1"))
    arkusz = {}
    for r in baza.execute(
        "SELECT dn_od_mm, dlugosc_sztuki_m, ilosc_projekt_m FROM material_item WHERE dn_od_mm IS NOT NULL"
    ):
        od, sztuka, ilosc = r["dn_od_mm"], f(r["dlugosc_sztuki_m"]), float(r["ilosc_projekt_m"] or 0)
        if sztuka == 3.0 or od not in arkusz:  # wariant /3 reprezentuje cale zapotrzebowanie
            arkusz[od] = arkusz.get(od, 0) + ilosc if sztuka == 3.0 else ilosc
    print(f"    {'DN':>6} {'OD':>6} {'PDF [m]':>10} {'XLSX [m]':>10} {'roznica':>10}")
    for dn in sorted(pdf):
        od = PROFIL_NA_OD.get(dn, dn)
        x = arkusz.get(od)
        roznica = f"{x - pdf[dn]:+.1f}" if x is not None else "-"
        znacznik = "  <-- NIEDOBOR" if x is not None and x < pdf[dn] else ""
        print(f"    {dn:>6} {od:>6} {pdf[dn]:>10} {x if x is not None else '-':>10} {roznica:>10}{znacznik}")
    bez_dn_odc = baza.execute("SELECT count(*), round(sum(dlugosc_m),1) FROM segment WHERE dn_mm IS NULL").fetchone()
    print(f"    Zastrzezenie: {bez_dn_odc[0]} odcinkow ({bez_dn_odc[1]} m) nie ma srednicy,")
    print("    wiec kolumna PDF jest dolnym oszacowaniem dla pozostalych srednic.")

    print("\n  Arkusz Studnie - kontrola wlasnej legendy (Gl = Rz.g. - Rz.d.):")
    zlamane = []
    for dane in ark["studnie"].values():
        kod = dane.get("B")
        rzg, rzd, gl = liczba(dane.get("F")), liczba(dane.get("G")), liczba(dane.get("H"))
        if not kod or None in (rzg, rzd, gl):
            continue
        if abs((rzg - rzd) - gl) > 0.015:
            zlamane.append(f"{bez_sss(kod):<10} Rz.g {rzg} - Rz.d {rzd} = {rzg-rzd:.2f}, a Gl podane {gl}  "
                           f"[{(dane.get('D') or '')[:34]}]")
    print(f"  Wierszy lamiacych wlasna legende: {len(zlamane)}")
    lista(zlamane, limit)


def sekcja_osnowa(baza, ark, limit):
    naglowek("OSNOWA GEODEZYJNA - kompletnosc i metadane")
    tekst = OSNOWA.read_text(encoding="utf-8", errors="replace").splitlines()
    punkty = []
    for linia in tekst:
        czesci = linia.strip().split(",")
        if len(czesci) == 4:
            try:
                punkty.append((czesci[0], float(czesci[1]), float(czesci[2]), float(czesci[3])))
            except ValueError:
                pass
    print(f"\n  Punktow w pliku: {len(punkty)}")
    print(f"  Pierwsza linia pliku: {tekst[0]!r}")
    print("  Kolumny: nazwa, X, Y, H - BEZ naglowka i bez metadanych.")
    print("  Brak: ukladu wysokosciowego, klasy/dokladnosci, rodzaju stabilizacji,")
    print("        daty pomiaru, opisu topograficznego, numeru operatu.")
    print()
    print("  RYZYKO NR 1 - uklad wysokosciowy niezadeklarowany.")
    print("  Roznica Kronsztadt'86 <-> PL-EVRF2007-NH to srednio 0.1649 m.")
    print("  Kronsztadt'86 przestal obowiazywac w pomiarach 1.01.2024.")

    numery = sorted(int(re.sub(r"\D", "", n)) for n, *_ in punkty)
    luki = [i for i in range(numery[0], numery[-1] + 1) if i not in set(numery)]
    print(f"\n  Numeracja: o{numery[0]} .. o{numery[-1]}, luk w numeracji: {len(luki)}")
    print("  Nic nie mowi, czy to wybor punktow dla tego odcinka, czy punkty zniszczone.")

    dystanse = sorted(
        math.dist((punkty[i][1], punkty[i][2]), (punkty[i + 1][1], punkty[i + 1][2]))
        for i in range(len(punkty) - 1)
    )
    print(f"\n  Odleglosc miedzy kolejnymi punktami: min {dystanse[0]:.1f} m, "
          f"mediana {dystanse[len(dystanse)//2]:.1f} m, max {dystanse[-1]:.1f} m")

    miejsc = max(len(str(h).split(".")[-1]) for *_, h in punkty)
    print(f"  Wysokosci zapisane z {miejsc} miejscami po przecinku - dokladnosc pozorna")
    print("  przy nieznanym bledzie punktu.")

    typy = collections.Counter(t for (t,) in baza.execute("SELECT typ FROM survey_point"))
    uklady = collections.Counter(u for (u,) in baza.execute("SELECT uklad FROM survey_point"))
    print(f"\n  W bazie: typ {dict(typy)}, uklad {dict(uklady)}")
    print("  Wszystkie punkty maja komplet X, Y, H - to osnowa realizacyjna")
    print("  (poziomo-wysokosciowa), a nie repery niwelacyjne. Typ 'REPER' zaciera")
    print("  rozroznienie, ktore decyduje o tym, co wolno z punktu wyznaczac.")


SEKCJE = {
    "spadki": sekcja_spadki,
    "przykrycie": sekcja_przykrycie,
    "rozstaw": sekcja_rozstaw,
    "wyloty": sekcja_wyloty,
    "odczyt": sekcja_odczyt,
    "topologia": sekcja_topologia,
    "braki": sekcja_braki,
    "material": sekcja_material,
    "osnowa": sekcja_osnowa,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sekcja", nargs="+", choices=sorted(SEKCJE), help="tylko wybrane grupy kontroli")
    parser.add_argument("--limit", type=int, default=25, help="ile pozycji listy pokazac (0 = wszystkie)")
    parser.add_argument("--baza", type=Path, default=BAZA)
    parser.add_argument("--xlsx", type=Path, default=XLSX)
    args = parser.parse_args()

    for sciezka in (args.baza, args.xlsx, OSNOWA):
        if not sciezka.exists():
            print(f"BLAD: brak pliku {sciezka}", file=sys.stderr)
            return 1

    baza = sqlite3.connect(f"file:{args.baza}?mode=ro", uri=True)
    baza.row_factory = sqlite3.Row
    ark = wczytaj_xlsx(args.xlsx)

    print("AUDYT BRANZOWY ODWODNIENIA DK29")
    print(f"baza:   {args.baza}")
    print(f"arkusz: {args.xlsx}")
    print(f"osnowa: {OSNOWA}")
    print("\nRaport slowny: docs/audyt-branzowy-dk29.md")

    for nazwa in (args.sekcja or SEKCJE):
        SEKCJE[nazwa](baza, ark, args.limit)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
