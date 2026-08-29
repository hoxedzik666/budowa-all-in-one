"""Zapis wycietej sieci do formatow, ktore czyta ktos poza ta aplikacja.

Trzy odbiorcy, trzy formaty:

  * **GeoJSON** - geodeta i QGIS,
  * **DXF**     - projektant i CAD,
  * **CSV**     - tyczenie z tachimetru: nazwa, X, Y.

Uklad wspolrzednych zalezy od tego, czy arkusz zostal zwiazany z terenem
(`georef.py`). Jesli tak - wychodzi PL-2000/5 i plik otwiera sie na swoim
miejscu na mapie. Jesli nie - wychodza wspolrzedne strony w metrach, liczone
po skali rysunku. **Ktora to wersja, jest zapisane w samym pliku**, zeby nikt
nie wzial jednej za druga.

DXF piszemy sami, w wersji R12. Format jest wiekowy i gadatliwy, ale czyta go
kazdy program CAD bez wyjatku, a caly zapis to kilkadziesiat linii - mniej niz
koszt kolejnej zaleznosci.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

from app.services.georef import Przeksztalcenie
from app.services.plan_wektor import MM_NA_PUNKT, Polilinia, SiecStrony

UKLAD_GIS = "PL-2000/5"
EPSG_GIS = 2176


@dataclass
class Odwzorowanie:
    """Jak przeliczyc punkt rysunku na wspolrzedne w pliku wynikowym."""

    przeksztalcenie: Przeksztalcenie | None
    skala: int = 1000

    @property
    def w_ukladzie_panstwowym(self) -> bool:
        return self.przeksztalcenie is not None

    @property
    def opis(self) -> str:
        if self.przeksztalcenie is None:
            return (f"wspolrzedne strony PDF przeliczone na metry wg skali "
                    f"1:{self.skala} - arkusz nie jest zwiazany z terenem")
        return f"{UKLAD_GIS} (EPSG:{EPSG_GIS})"

    def punkt(self, x_pt: float, y_pt: float) -> tuple[float, float]:
        """Zwraca (wschod, polnoc) - czyli kolejnosc (x, y) przyjeta w GIS."""
        if self.przeksztalcenie is not None:
            polnoc, wschod = self.przeksztalcenie.na_teren(x_pt, y_pt)
            return wschod, polnoc
        metry = MM_NA_PUNKT * self.skala / 1000.0
        # Os Y rysunku rosnie w dol; odwracamy, zeby polnoc byla u gory.
        return round(x_pt * metry, 3), round(-y_pt * metry, 3)


def _wspolrzedne(polilinia: Polilinia, odwz: Odwzorowanie) -> list[list[float]]:
    return [list(odwz.punkt(x, y)) for x, y in polilinia.punkty]


# ------------------------------------------------------------------ GeoJSON


def do_geojson(siec: SiecStrony, odwz: Odwzorowanie) -> str:
    obiekty = []
    for numer, polilinia in enumerate(siec.polilinie, 1):
        obiekty.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": _wspolrzedne(polilinia, odwz)},
            "properties": {
                "id": f"s{siec.nr_strony}-p{numer}",
                "rodzaj": "przewod",
                "styl": polilinia.styl,
                "dlugosc_m": polilinia.dlugosc_m(siec.skala),
                "nr_strony": siec.nr_strony,
            },
        })

    for numer, (x, y) in enumerate(siec.wezly, 1):
        obiekty.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": list(odwz.punkt(x, y))},
            "properties": {"id": f"s{siec.nr_strony}-w{numer}", "rodzaj": "wezel",
                           "nr_strony": siec.nr_strony},
        })

    for etykieta in siec.etykiety:
        obiekty.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": list(odwz.punkt(etykieta.x_pt, etykieta.y_pt))},
            "properties": {"rodzaj": "kilometraz", "tekst": etykieta.tekst,
                           "kilometraz_m": etykieta.kilometraz_m,
                           "nr_strony": siec.nr_strony},
        })

    kolekcja = {
        "type": "FeatureCollection",
        # Skad te dane i w czym sa - zeby plik bronil sie sam, bez tej rozmowy.
        "nazwa": f"Plany sytuacyjne, strona {siec.nr_strony}",
        "uklad": odwz.opis,
        "zrodlo": "wyciete z rysunku wektorowego po stylu kreski; kody obiektow "
                  "nie sa zapisane na planie i nie sa tu przypisane",
        "features": obiekty,
    }
    if odwz.w_ukladzie_panstwowym:
        kolekcja["crs"] = {"type": "name",
                           "properties": {"name": f"urn:ogc:def:crs:EPSG::{EPSG_GIS}"}}
    return json.dumps(kolekcja, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------- CSV


def do_csv(siec: SiecStrony, odwz: Odwzorowanie) -> str:
    bufor = io.StringIO()
    zapis = csv.writer(bufor, delimiter=";", lineterminator="\n")
    zapis.writerow([f"# uklad: {odwz.opis}"])
    zapis.writerow([f"# strona planu: {siec.nr_strony}, skala 1:{siec.skala}"])
    zapis.writerow(["nazwa", "X_polnoc", "Y_wschod", "x_pt", "y_pt", "rodzaj"])

    for numer, (x, y) in enumerate(siec.wezly, 1):
        wschod, polnoc = odwz.punkt(x, y)
        zapis.writerow([f"s{siec.nr_strony}w{numer}", f"{polnoc:.3f}", f"{wschod:.3f}",
                        f"{x:.2f}", f"{y:.2f}", "wezel"])

    for etykieta in siec.etykiety:
        wschod, polnoc = odwz.punkt(etykieta.x_pt, etykieta.y_pt)
        zapis.writerow([etykieta.tekst.replace(" ", ""), f"{polnoc:.3f}", f"{wschod:.3f}",
                        f"{etykieta.x_pt:.2f}", f"{etykieta.y_pt:.2f}", "kilometraz"])
    return bufor.getvalue()


# ---------------------------------------------------------------------- DXF


def _para(kod: int, wartosc) -> str:
    return f"{kod}\n{wartosc}\n"


def do_dxf(siec: SiecStrony, odwz: Odwzorowanie) -> str:
    """DXF R12 - najstarszy format, ktory czyta absolutnie kazdy CAD."""
    czesci: list[str] = []

    czesci.append(_para(0, "SECTION") + _para(2, "HEADER"))
    czesci.append(_para(9, "$ACADVER") + _para(1, "AC1009"))
    czesci.append(_para(9, "$INSUNITS") + _para(70, 6))          # metry
    czesci.append(_para(0, "ENDSEC"))

    czesci.append(_para(0, "SECTION") + _para(2, "TABLES"))
    czesci.append(_para(0, "TABLE") + _para(2, "LAYER") + _para(70, 3))
    for nazwa, kolor in (("KD_PRZEWODY", 3), ("KD_WEZLY", 1), ("KILOMETRAZ", 5)):
        czesci.append(_para(0, "LAYER") + _para(2, nazwa) + _para(70, 0)
                      + _para(62, kolor) + _para(6, "CONTINUOUS"))
    czesci.append(_para(0, "ENDTAB") + _para(0, "ENDSEC"))

    czesci.append(_para(0, "SECTION") + _para(2, "ENTITIES"))

    for polilinia in siec.polilinie:
        punkty = _wspolrzedne(polilinia, odwz)
        czesci.append(_para(0, "POLYLINE") + _para(8, "KD_PRZEWODY")
                      + _para(66, 1) + _para(70, 0))
        for wschod, polnoc in punkty:
            czesci.append(_para(0, "VERTEX") + _para(8, "KD_PRZEWODY")
                          + _para(10, f"{wschod:.3f}") + _para(20, f"{polnoc:.3f}")
                          + _para(30, "0.0"))
        czesci.append(_para(0, "SEQEND") + _para(8, "KD_PRZEWODY"))

    for x, y in siec.wezly:
        wschod, polnoc = odwz.punkt(x, y)
        czesci.append(_para(0, "POINT") + _para(8, "KD_WEZLY")
                      + _para(10, f"{wschod:.3f}") + _para(20, f"{polnoc:.3f}")
                      + _para(30, "0.0"))

    for etykieta in siec.etykiety:
        wschod, polnoc = odwz.punkt(etykieta.x_pt, etykieta.y_pt)
        czesci.append(_para(0, "TEXT") + _para(8, "KILOMETRAZ")
                      + _para(10, f"{wschod:.3f}") + _para(20, f"{polnoc:.3f}")
                      + _para(30, "0.0") + _para(40, "2.5")
                      + _para(1, etykieta.tekst))

    czesci.append(_para(0, "ENDSEC") + _para(0, "EOF"))
    return "".join(czesci)


# ------------------------------------------------------------------- cache


def do_json(siec: SiecStrony) -> str:
    """Zrzut wyniku wycinania - zeby nie liczyc go po raz drugi.

    Wyciecie jednej strony to kilka sekund (do 225 tysiecy sciezek), calego
    pliku - ponad dwie minuty. To za dlugo na zadanie HTTP, wiec wynik ladzie
    na dysku i stamtad go czytamy.
    """
    return json.dumps({
        "nr_strony": siec.nr_strony,
        "szerokosc_pt": siec.szerokosc_pt,
        "wysokosc_pt": siec.wysokosc_pt,
        "skala": siec.skala,
        "sciezek_na_stronie": siec.sciezek_na_stronie,
        "polilinie": [{"styl": p.styl, "punkty": [[round(x, 2), round(y, 2)]
                                                  for x, y in p.punkty]}
                      for p in siec.polilinie],
        "wezly": [[round(x, 2), round(y, 2)] for x, y in siec.wezly],
        "etykiety": [e.to_dict() for e in siec.etykiety],
    }, ensure_ascii=False)


def z_json(tekst: str) -> SiecStrony:
    from app.services.plan_wektor import Etykieta

    dane = json.loads(tekst)
    return SiecStrony(
        nr_strony=dane["nr_strony"],
        szerokosc_pt=dane["szerokosc_pt"],
        wysokosc_pt=dane["wysokosc_pt"],
        skala=dane["skala"],
        polilinie=[Polilinia([(x, y) for x, y in p["punkty"]], p["styl"])
                   for p in dane["polilinie"]],
        wezly=[(x, y) for x, y in dane["wezly"]],
        etykiety=[Etykieta(e["tekst"], e["x_pt"], e["y_pt"], e.get("kilometraz_m"))
                  for e in dane["etykiety"]],
        sciezek_na_stronie=dane.get("sciezek_na_stronie", 0),
    )


FORMATY = {
    "geojson": (do_geojson, "application/geo+json", ".geojson"),
    "dxf": (do_dxf, "application/dxf", ".dxf"),
    "csv": (do_csv, "text/csv; charset=utf-8", ".csv"),
}


def zapisz(siec: SiecStrony, odwz: Odwzorowanie, format_: str) -> tuple[str, str, str]:
    """Zwraca (tresc, typ MIME, rozszerzenie)."""
    if format_ not in FORMATY:
        raise ValueError(f"Nie znam formatu {format_!r}. Dostepne: {sorted(FORMATY)}")
    funkcja, mime, rozszerzenie = FORMATY[format_]
    return funkcja(siec, odwz), mime, rozszerzenie
