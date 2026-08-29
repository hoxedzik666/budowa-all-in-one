"""Import danych zrodlowych do bazy.

Trzy zrodla, trzy role:
  * "Profile Scalone.pdf"      - geometria profili: wezly, rzedne, odcinki.
  * "Material.xlsx"            - tabelaryczna kontrola + jawny graf polaczen
                                 (kolumna "Odbiornik" przy wpustach) + materialy.
  * "!!_DK29_osnowa_ok_v1.txt" - repery do modulu niwelatora.

PDF jest zrodlem geometrii, XLSX zrodlem uzupelnien i walidatorem. Rozbieznosci
miedzy nimi nie sa ukrywane - lecza do ImportRun.ostrzezenia.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from app.extensions import db
from app.models import (
    Branza,
    Connection,
    ImportRun,
    MaterialItem,
    NetworkObject,
    ObjectOccurrence,
    Profile,
    Segment,
    Sheet,
    SurveyPoint,
    TypObiektu,
    TypOdniesienia,
    ZrodloDanych,
)
from app.models.enums import PREFIX_TYP
from app.services.pdf_profile_parser import (
    RE_KAT,
    RE_RZ_STUDNI,
    RE_SREDNICA,
    parsuj_profile,
)

RE_KOD_W_TEKSCIE = re.compile(r"\b(Wyl|SEP|Ws|Wo|Wp|Tr|KT|Ł|D|O)\s?(\d+[a-z]?)\b")

# Slowa kluczowe z opisu -> typ obiektu. Maja pierwszenstwo przed prefiksem kodu,
# bo opis pochodzi wprost od projektanta.
OPIS_TYP = [
    ("separator", TypObiektu.SEPARATOR),
    ("osadnik", TypObiektu.OSADNIK),
    ("piaskownik", TypObiektu.STUDNIA),
    ("studnia", TypObiektu.STUDNIA),
    ("studzienka", TypObiektu.STUDNIA),
    ("wpust", TypObiektu.WPUST),
    ("wylot", TypObiektu.WYLOT),
    ("trójnik", TypObiektu.TROJNIK),
    ("trojnik", TypObiektu.TROJNIK),
    ("łuk", TypObiektu.LUK),
    ("ściek", TypObiektu.SCIEK_SKARPOWY),
]


# Pola obiektu, ktore pochodza wprost z rysunku profilu. Przy ponownym imporcie
# musza wrocic do stanu "puste", inaczej zapis `if wartosc is None` nigdy ich nie
# odswiezy i poprawka w dokumentacji nie dojdzie do bazy. Nie ruszamy kodu, typu,
# wskazanych pozycji na planie ani niczego, co przyszlo z arkusza materialowego.
#
# `rzedna_terenu_proj` i `rzedna_dna_studni` bywaja uzupelniane rowniez z arkusza
# materialowego, wiec ich wyzerowanie znaczy, ze po imporcie profili trzeba
# przepuscic jeszcze arkusz. `import-wszystko` robi to sam, a `import-profile`
# uruchomiony osobno o tym przypomina.
POLA_Z_PDF = (
    "rzedna_dna_kanalu",
    "rzedna_dna_studni",
    "rzedna_terenu_istn",
    "rzedna_terenu_proj",
    "zaglebienie",
)


def _zeruj_pola_z_pdf() -> None:
    """Wyczysc rzedne pochodzace z profili przed ponownym ich wczytaniem.

    Bez tego `rzedna_dna_kanalu`, liczona jako minimum ze wszystkich profili,
    kumulowalaby sie przez kolejne przebiegi importu: raz obnizona nigdy juz
    by nie wzrosla, choc rysunek podawalby wyzsza wartosc.
    """
    from sqlalchemy import update

    db.session.execute(
        update(NetworkObject)
        .where(NetworkObject.zrodlo == ZrodloDanych.PDF_PROFIL)
        .values({pole: None for pole in POLA_Z_PDF})
    )


def _sha256(sciezka: Path) -> str:
    h = hashlib.sha256()
    with open(sciezka, "rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def _typ_obiektu(kod: str, opis: str | None, branza: str = "KD") -> TypObiektu:
    if opis:
        niski = opis.lower()
        for slowo, typ in OPIS_TYP:
            if slowo in niski:
                return typ
    for prefiks, typ in PREFIX_TYP:
        if kod.startswith(prefiks):
            return typ
    if kod.startswith("Ł"):
        return TypObiektu.LUK
    if branza == "KT":
        return TypObiektu.WEZEL_KT
    return TypObiektu.INNY


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


# ------------------------------------------------------------------ osnowa


def importuj_osnowe(sciezka: str | Path) -> ImportRun:
    """Plik CSV bez naglowka: nazwa,X,Y,H (PL-2000 strefa 5)."""
    sciezka = Path(sciezka)
    bieg = ImportRun(plik=sciezka.name, sha256=_sha256(sciezka), typ_importu="OSNOWA")
    db.session.add(bieg)

    ostrzezenia: list[dict] = []
    dodane = 0
    for nr, linia in enumerate(sciezka.read_text(encoding="utf-8-sig").splitlines(), 1):
        linia = linia.strip()
        if not linia:
            continue
        czesci = [c.strip() for c in linia.split(",")]
        if len(czesci) < 4:
            ostrzezenia.append({"wiersz": nr, "problem": "za malo kolumn", "tresc": linia})
            continue
        nazwa, x, y, h = czesci[0], _num(czesci[1]), _num(czesci[2]), _num(czesci[3])
        punkt = db.session.scalar(select(SurveyPoint).where(SurveyPoint.nazwa == nazwa))
        if punkt is None:
            punkt = SurveyPoint(nazwa=nazwa)
            db.session.add(punkt)
            dodane += 1
        punkt.x, punkt.y, punkt.h = x, y, h
        punkt.uklad = "PL-2000/5"
        punkt.typ = "REPER"
        punkt.zrodlo = ZrodloDanych.TXT_OSNOWA.value

    bieg.liczba_obiektow = dodane
    bieg.ostrzezenia = ostrzezenia
    bieg.liczba_ostrzezen = len(ostrzezenia)
    bieg.statystyki = {"punktow": dodane}
    bieg.zakonczono = datetime.now(timezone.utc)
    db.session.commit()
    return bieg


# ------------------------------------------------------------------ PDF


def importuj_profile(sciezka: str | Path, wyczysc: bool = True) -> ImportRun:
    sciezka = Path(sciezka)
    bieg = ImportRun(plik=sciezka.name, sha256=_sha256(sciezka), typ_importu="PROFILE_PDF")
    db.session.add(bieg)
    db.session.flush()

    if wyczysc:
        db.session.execute(delete(Segment))
        db.session.execute(delete(ObjectOccurrence))
        # Tylko wlasne polaczenia. Wczesniej lecialo `delete(Connection)` bez
        # warunku, wiec import profili kasowal tez graf z arkusza materialowego
        # i kompletnosc danych zalezala od kolejnosci komend.
        db.session.execute(
            delete(Connection).where(Connection.zrodlo == ZrodloDanych.PDF_PROFIL)
        )
        db.session.execute(delete(Profile))
        db.session.execute(delete(Sheet).where(Sheet.plik == sciezka.name))
        _zeruj_pola_z_pdf()
        db.session.flush()

    wynik = parsuj_profile(sciezka)
    ostrzezenia: list[dict] = list(wynik.ostrzezenia)

    # --- arkusze
    arkusze: dict[int, Sheet] = {}
    for meta in wynik.strony:
        ark = Sheet(
            plik=sciezka.name,
            nr_strony=meta["nr_strony"],
            szerokosc_pt=meta["szerokosc"],
            wysokosc_pt=meta["wysokosc"],
            branza=Branza.KT if meta["typ_odniesienia"] == "OS_PRZEWODU" else Branza.KD,
        )
        db.session.add(ark)
        arkusze[meta["nr_strony"]] = ark
    db.session.flush()

    # --- obiekty kanoniczne
    obiekty: dict[str, NetworkObject] = {}

    def obiekt(kod: str, wezel=None, branza: str = "KD") -> NetworkObject:
        ob = obiekty.get(kod)
        if ob is None:
            ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
        if ob is None:
            ob = NetworkObject(kod=kod, typ=_typ_obiektu(kod, wezel.opis if wezel else None, branza))
            db.session.add(ob)
            db.session.flush()  # potrzebne ob.id do wystapien i polaczen
        obiekty[kod] = ob
        return ob

    # Naturalne klucze polaczen dodanych w tym przebiegu - ten sam wlot bywa
    # opisany na kilku profilach.
    widziane_polaczenia: set = set()

    liczba_profili = 0
    for prof in wynik.profile:
        rekord = Profile(
            oznaczenie=prof.oznaczenie,
            sheet_id=arkusze[prof.nr_strony].id if prof.nr_strony in arkusze else None,
            branza=Branza[prof.branza] if prof.branza in Branza.__members__ else Branza.KD,
            typ_odniesienia=TypOdniesienia[prof.typ_odniesienia],
            poziom_porownawczy=prof.poziom_porownawczy,
            dlugosc_calkowita_m=prof.dlugosc_calkowita_m,
            blok_index=prof.blok_index,
            bbox={"x_od": round(prof.x_od, 1), "x_do": round(prof.x_do, 1)},
        )
        db.session.add(rekord)
        db.session.flush()
        liczba_profili += 1

        for o in prof.ostrzezenia:
            ostrzezenia.append({"strona": prof.nr_strony, "profil": prof.oznaczenie, "problem": o})

        wezly_db: dict[str, NetworkObject] = {}
        for kolejnosc, w in enumerate(prof.wezly):
            ob = obiekt(w.kod, w, prof.branza)
            wezly_db[w.kod] = ob

            # Kanoniczna rzedna dna = najnizsza ze wszystkich profili (odplyw).
            if w.rzedna_dna is not None:
                if ob.rzedna_dna_kanalu is None or w.rzedna_dna < float(ob.rzedna_dna_kanalu):
                    ob.rzedna_dna_kanalu = w.rzedna_dna
                    ob.zaglebienie = w.zaglebienie
            for pole, wartosc in (
                ("rzedna_terenu_proj", w.rzedna_terenu_proj),
                ("rzedna_terenu_istn", w.rzedna_terenu_istn),
                ("rzedna_dna_studni", w.rzedna_dna_studni),
                ("srednica_studni_mm", w.srednica_studni_mm),
                ("opis", w.opis),
            ):
                if wartosc is not None and getattr(ob, pole) is None:
                    setattr(ob, pole, wartosc)
            if w.opis and ob.typ in (TypObiektu.INNY,):
                ob.typ = _typ_obiektu(w.kod, w.opis, prof.branza)
            if w.alias:
                ob.uwagi = f"alias: {w.alias}"

            db.session.add(ObjectOccurrence(
                profil_id=rekord.id, obiekt_id=ob.id, kolejnosc=kolejnosc,
                hektometr=w.hektometr, rzedna_dna=w.rzedna_dna, zaglebienie=w.zaglebienie,
                rzedna_terenu_proj=w.rzedna_terenu_proj, rzedna_terenu_istn=w.rzedna_terenu_istn,
                opis=w.opis, bbox=w.bbox,
            ))

            # Dodatkowe wloty do wezla (studnia z kilkoma rurami na roznych rzednych).
            for rz in w.dodatkowe_wloty:
                _dodaj_polaczenie(Connection(
                    obiekt_id=ob.id, rzedna=rz, kierunek="DOPLYW",
                    opis="dodatkowa rzedna dna z profilu " + prof.oznaczenie,
                ), widziane_polaczenia)
            for adn in w.adnotacje:
                _zapisz_adnotacje(ob, adn, widziane_polaczenia)

        db.session.flush()

        for kolejnosc, o in enumerate(prof.odcinki):
            a, b = wezly_db.get(o.od), wezly_db.get(o.do)
            if a is None or b is None or a.id == b.id:
                continue
            db.session.add(Segment(
                profil_id=rekord.id, obiekt_od_id=a.id, obiekt_do_id=b.id,
                kolejnosc=kolejnosc, dlugosc_m=o.dlugosc_m, dn_mm=o.dn_mm,
                spadek_promile=abs(o.spadek_promile) if o.spadek_promile is not None else None,
                material=o.material, rzedna_dna_od=o.rzedna_od, rzedna_dna_do=o.rzedna_do,
                surowe=o.surowe,
            ))
            # Srednica krolca obiektu - z odcinka, jesli obiekt jej nie ma.
            for ob in (a, b):
                if ob.dn_mm is None and o.dn_mm:
                    ob.dn_mm = o.dn_mm

    db.session.flush()
    _uzgodnij_zaglebienia(ostrzezenia)
    db.session.flush()

    from app.services.walidacja import sprawdz_dane

    raport = sprawdz_dane(oznacz=True)
    ostrzezenia.extend(p.to_dict() for p in raport.problemy)

    bieg.liczba_profili = liczba_profili
    bieg.liczba_obiektow = db.session.scalar(select(func.count()).select_from(NetworkObject))
    bieg.liczba_odcinkow = db.session.scalar(select(func.count()).select_from(Segment))
    bieg.ostrzezenia = ostrzezenia[:3000]
    bieg.liczba_ostrzezen = len(ostrzezenia)
    bieg.statystyki = {
        "stron": len(wynik.strony),
        "wezlow_na_profilach": wynik.liczba_wezlow,
        "odcinkow_z_parsera": wynik.liczba_odcinkow,
        **raport.statystyki,
        "problemy_wg_kategorii": raport.wg_kategorii,
    }
    bieg.zakonczono = datetime.now(timezone.utc)
    db.session.commit()
    return bieg


def _uzgodnij_zaglebienia(ostrzezenia: list[dict]) -> None:
    """Dopilnuj niezmiennika zaglebienie = teren proj. - dno kanalu.

    Trojka rzednych trafia do bazy z trzech niezaleznych miejsc rysunku, wiec
    potrafi sie rozjechac. Rzedne terenu i dna sa mierzone, zaglebienie jest
    ich roznica - wiec to zaglebienie poprawiamy, nie odwrotnie. Kazda poprawka
    wieksza niz 2 cm trafia do ostrzezen, bo oznacza, ze cos w odczycie rysunku
    nie zagralo i warto na to spojrzec.
    """
    from app.services.walidacja import TOL_NIEZMIENNIKA_M

    for ob in db.session.scalars(select(NetworkObject)):
        if ob.rzedna_terenu_proj is None or ob.rzedna_dna_kanalu is None:
            continue
        poprawne = round(float(ob.rzedna_terenu_proj) - float(ob.rzedna_dna_kanalu), 3)
        obecne = float(ob.zaglebienie) if ob.zaglebienie is not None else None
        if obecne is not None and abs(obecne - poprawne) > TOL_NIEZMIENNIKA_M:
            ostrzezenia.append({
                "typ": "ZAGLEBIENIE_POPRAWIONE", "obiekt": ob.kod,
                "z_rysunku": obecne, "z_rzednych": poprawne,
                "roznica": round(poprawne - obecne, 3),
            })
        ob.zaglebienie = poprawne


def _klucz_polaczenia(polaczenie: Connection) -> tuple:
    """Naturalny klucz wiersza - ten sam, ktorego pilnuje indeks w bazie."""
    return (
        polaczenie.obiekt_id,
        polaczenie.obiekt_zrodlowy_kod or "",
        polaczenie.dn_mm if polaczenie.dn_mm is not None else -1,
        float(polaczenie.rzedna) if polaczenie.rzedna is not None else -9999.0,
        polaczenie.kierunek,
        (polaczenie.opis or "")[:120],
    )


def _dodaj_polaczenie(polaczenie: Connection, widziane: set) -> bool:
    """Dopisz polaczenie, o ile identyczne nie padlo juz w tym imporcie.

    Ten sam wlot bywa opisany na kilku profilach - np. wlaczenie Wp466 do Wyl6
    widnieje i na profilu wylotu, i na profilu wpustu. To jedno polaczenie,
    nie dwa, wiec powtorzenie pomijamy zamiast dublowac wiersz.
    """
    klucz = _klucz_polaczenia(polaczenie)
    if klucz in widziane:
        return False
    widziane.add(klucz)
    db.session.add(polaczenie)
    return True


def _zapisz_adnotacje(ob: NetworkObject, tekst: str, widziane: set) -> None:
    """Adnotacje typu "Proj. wlaczenie kanalu Wp133 Ø400, Rz.d.=43.46"."""
    dn = RE_SREDNICA.search(tekst)
    rz = RE_RZ_STUDNI.search(tekst)
    kod = RE_KOD_W_TEKSCIE.search(tekst)
    kat = RE_KAT.search(tekst)
    if not (dn or rz or kat):
        return
    _dodaj_polaczenie(Connection(
        obiekt_id=ob.id,
        obiekt_zrodlowy_kod=f"{kod.group(1)}{kod.group(2)}" if kod else None,
        dn_mm=int(dn.group(1)) if dn else None,
        rzedna=_num(rz.group(1)) if rz else None,
        kat_stopnie=_num(kat.group(1)) if kat else None,
        oznaczenie_kanalu=kat.group(2) if kat and kat.group(2) else None,
        opis=tekst[:500],
    ), widziane)
