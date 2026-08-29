"""Wykaz materialow dla pojedynczego odcinka.

Arkusz RURY to **magazyn globalny** calej budowy, a nie przedmiar odcinkowy -
nie ma w nim wiersza "na odcinek Wyl101-D155 potrzeba tyle a tyle". Wykaz trzeba
policzyc: srednica i dlugosc odcinka -> pozycje katalogowe, plus obiekty na obu
koncach.

Powiazanie odcinka z katalogiem idzie przez srednice ZEWNETRZNA (OD), bo tak sa
opisane rury PRAGMA - patrz `app/services/rury.py`.
"""
from __future__ import annotations

import re

from sqlalchemy import select

from app.extensions import db
from app.models import MaterialItem, NetworkObject, TypObiektu
from app.services.rury import przelicz, srednica_katalogowa

RE_SN = re.compile(r"\bSN\s*(\d{1,2})\b", re.I)

# Typy obiektow, ktore sa osobna pozycja materialowa (a nie rura).
OBIEKTY_MATERIALOWE = {
    TypObiektu.STUDNIA: "studnia",
    TypObiektu.WPUST: "wpust",
    TypObiektu.WYLOT: "wylot",
    TypObiektu.SEPARATOR: "separator",
    TypObiektu.OSADNIK: "osadnik",
    TypObiektu.TROJNIK: "trójnik",
    TypObiektu.LUK: "łuk",
}


def klasa_sn_odcinka(odcinek) -> str | None:
    """Klasa sztywnosci rury - projektant zapisuje ja w uwagach obiektu."""
    for ob in (odcinek.obiekt_od, odcinek.obiekt_do):
        if ob is None:
            continue
        for tekst in (ob.uwagi, ob.opis):
            if tekst and (m := RE_SN.search(tekst)):
                return f"SN{m.group(1)}"
    return None


def pozycje_katalogowe(dn_od_mm: int | None, klasa_sn: str | None = None) -> list[MaterialItem]:
    """Pozycje z arkusza RURY pasujace do tej srednicy."""
    if dn_od_mm is None:
        return []
    q = select(MaterialItem).where(MaterialItem.dn_od_mm == dn_od_mm)
    pozycje = list(db.session.scalars(q.order_by(MaterialItem.dlugosc_sztuki_m)))
    if klasa_sn:
        pasujace = [p for p in pozycje if p.klasa_sn == klasa_sn]
        if pasujace:
            return pasujace
    return pozycje


def wykaz_dla_odcinka(odcinek) -> dict:
    """Kompletny wykaz materialow potrzebnych na jeden odcinek."""
    dlugosc = float(odcinek.dlugosc_m) if odcinek.dlugosc_m is not None else None
    dn_od = srednica_katalogowa(odcinek.dn_mm)
    sn = klasa_sn_odcinka(odcinek)

    rury = przelicz(dlugosc, odcinek.dn_mm)
    katalog = pozycje_katalogowe(dn_od, sn)

    # Do kazdej dlugosci handlowej dopnij pozycje katalogowa i stan dostaw.
    katalog_wg_dlugosci = {}
    for p in katalog:
        if p.dlugosc_sztuki_m is not None:
            katalog_wg_dlugosci[float(p.dlugosc_sztuki_m)] = p

    for wariant in rury["warianty"]:
        for poz in wariant["pozycje"]:
            k = katalog_wg_dlugosci.get(poz["dlugosc_m"])
            poz["katalog"] = k.to_dict() if k else None

    obiekty = []
    for ob, rola in ((odcinek.obiekt_od, "początek"), (odcinek.obiekt_do, "koniec")):
        if ob is None:
            continue
        obiekty.append({
            "kod": ob.kod,
            "rola": rola,
            "typ": ob.typ.value if ob.typ else None,
            "nazwa_materialowa": OBIEKTY_MATERIALOWE.get(ob.typ, "element"),
            "srednica_studni_mm": ob.srednica_studni_mm,
            "opis": ob.opis,
            "uwagi": ob.uwagi,
            "rzedna_dna_studni": float(ob.rzedna_dna_studni) if ob.rzedna_dna_studni is not None else None,
            "glebokosc_wykopu": ob.glebokosc_wykopu,
        })

    return {
        "odcinek": odcinek.nazwa,
        "dlugosc_m": dlugosc,
        "dn_profilowe": odcinek.dn_mm,
        "dn_katalogowe": dn_od,
        "klasa_sn": sn,
        "rury": rury,
        "katalog": [p.to_dict() for p in katalog],
        "obiekty": obiekty,
        "braki": _braki(odcinek, dn_od, katalog),
    }


def _braki(odcinek, dn_od, katalog) -> list[str]:
    """Czego nie da sie policzyc i dlaczego - lepiej powiedziec wprost."""
    braki = []
    if odcinek.dlugosc_m is None:
        braki.append("Odcinek nie ma zapisanej długości — rysunek jej nie podaje.")
    if odcinek.dn_mm is None:
        braki.append("Odcinek nie ma zapisanej średnicy — rysunek jej nie podaje.")
    elif not katalog:
        braki.append(
            f"W arkuszu RURY nie ma pozycji dla OD{dn_od} "
            f"(średnica z profilu Ø{odcinek.dn_mm})."
        )
    return braki


def zapotrzebowanie_zbiorcze(odcinki, wariant: str = "mieszany") -> dict:
    """Zbiorcze zapotrzebowanie z porownaniem do stanu dostaw z arkusza RURY."""
    from app.services.rury import podsumuj

    suma = podsumuj(odcinki, wariant)
    for wpis in suma["srednice"]:
        pozycje = pozycje_katalogowe(wpis["dn_katalogowe"])
        dostarczono = sum(float(p.ilosc_dostarczona_m or 0) for p in pozycje)
        wpis["dostarczono_m"] = round(dostarczono, 2)
        wpis["brakuje_m"] = round(wpis["material_m"] - dostarczono, 2)
        wpis["pozycje_katalogowe"] = [p.to_dict() for p in pozycje]
    return suma
