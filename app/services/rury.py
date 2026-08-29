"""Przelicznik zapotrzebowania na rury.

Wykonawca ma na budowie rury w dwoch dlugosciach handlowych: **3 m i 6 m**.
Kazda srednica z arkusza RURY wystepuje w obu wariantach.

Dlugosc do zamowienia bierzemy **os-os, wprost z profilu** - tak liczy przedmiar
i tak podaje projektant, wiec wynik zgadza sie z zestawieniem materialowym.
Wciecia w studnie pokrywa naturalny zapas wynikajacy z zaokraglenia do pelnych rur.

Liczymy trzy warianty:
  * same 3 m,
  * same 6 m,
  * mieszany - dobor minimalizujacy LICZBE SZTUK, przy remisie mniejszy odpad.

Gdy odcinek nie dzieli sie na cale rury, ostatnia sztuka jest **docinana** -
raportujemy dlugosc docinki, liczbe ciec i odpad.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Dlugosci handlowe rur posiadanych przez wykonawce.
DLUGOSCI_HANDLOWE_M = (3.0, 6.0)

# Rury PRAGMA opisane sa srednica ZEWNETRZNA (OD), a profil podaje nominalna.
# Dla wiekszosci srednic obie sa takie same, ale nie dla wszystkich.
PROFIL_NA_OD = {
    200: 200,
    250: 250,
    300: 315,   # DN300 -> OD315
    400: 400,
    500: 500,
    600: 630,   # DN600 -> OD630
    1000: 1000,
}

# Tolerancja na bledy zaokraglen dlugosci z rysunku (1 cm).
TOL_M = 0.01


def srednica_katalogowa(dn_profilowe: int | None) -> int | None:
    """Zamien srednice z profilu na srednice zewnetrzna z katalogu."""
    if dn_profilowe is None:
        return None
    return PROFIL_NA_OD.get(dn_profilowe, dn_profilowe)


@dataclass
class PozycjaRur:
    """Ile sztuk rury danej dlugosci."""

    dlugosc_m: float
    sztuk: int

    @property
    def razem_m(self) -> float:
        return round(self.dlugosc_m * self.sztuk, 3)

    def to_dict(self) -> dict:
        return {"dlugosc_m": self.dlugosc_m, "sztuk": self.sztuk, "razem_m": self.razem_m}


@dataclass
class WariantRur:
    """Jeden sposob pociecia odcinka na rury."""

    nazwa: str
    etykieta: str
    pozycje: list[PozycjaRur] = field(default_factory=list)
    dlugosc_odcinka_m: float = 0.0
    docinka_m: float = 0.0      # dlugosc kawalka, ktory trzeba odciac
    odpad_m: float = 0.0        # co zostaje z docinanej rury
    liczba_ciec: int = 0
    mozliwy: bool = True
    uwaga: str | None = None

    @property
    def sztuk_razem(self) -> int:
        return sum(p.sztuk for p in self.pozycje)

    @property
    def material_m(self) -> float:
        """Ile metrow rury trzeba wziac z magazynu (z odpadem wlacznie)."""
        return round(sum(p.razem_m for p in self.pozycje), 3)

    @property
    def opis_sztuk(self) -> str:
        czesci = [f"{p.sztuk} × {p.dlugosc_m:g} m" for p in self.pozycje if p.sztuk]
        return " + ".join(czesci) if czesci else "—"

    def to_dict(self) -> dict:
        return {
            "nazwa": self.nazwa,
            "etykieta": self.etykieta,
            "pozycje": [p.to_dict() for p in self.pozycje],
            "opis_sztuk": self.opis_sztuk,
            "sztuk_razem": self.sztuk_razem,
            "dlugosc_odcinka_m": self.dlugosc_odcinka_m,
            "material_m": self.material_m,
            "docinka_m": self.docinka_m,
            "odpad_m": self.odpad_m,
            "liczba_ciec": self.liczba_ciec,
            "mozliwy": self.mozliwy,
            "uwaga": self.uwaga,
        }


def _zbuduj(nazwa: str, etykieta: str, dlugosc: float,
            sztuki: dict[float, int]) -> WariantRur:
    """Zloz wariant z policzonych sztuk i dolicz docinke."""
    pozycje = [PozycjaRur(dl, n) for dl, n in sorted(sztuki.items(), reverse=True) if n]
    material = sum(p.razem_m for p in pozycje)
    nadmiar = round(material - dlugosc, 3)

    w = WariantRur(
        nazwa=nazwa, etykieta=etykieta, pozycje=pozycje,
        dlugosc_odcinka_m=round(dlugosc, 3),
    )
    if nadmiar > TOL_M:
        # Ostatnia rura idzie na docinke: uzywamy jej kawalka, reszta to odpad.
        najkrotsza_uzyta = min((p.dlugosc_m for p in pozycje), default=0.0)
        w.odpad_m = nadmiar
        w.docinka_m = round(najkrotsza_uzyta - nadmiar, 3)
        w.liczba_ciec = 1
    return w


def wariant_jednorodny(dlugosc_m: float, dlugosc_rury_m: float) -> WariantRur:
    """Odcinek ulozony z rur wylacznie jednej dlugosci."""
    n = max(1, math.ceil((dlugosc_m - TOL_M) / dlugosc_rury_m))
    return _zbuduj(
        nazwa=f"same_{dlugosc_rury_m:g}m",
        etykieta=f"same rury {dlugosc_rury_m:g} m",
        dlugosc=dlugosc_m,
        sztuki={dlugosc_rury_m: n},
    )


def wariant_mieszany(dlugosc_m: float,
                     dlugosci: tuple[float, ...] = DLUGOSCI_HANDLOWE_M) -> WariantRur:
    """Dobor minimalizujacy liczbe sztuk, przy remisie - mniejszy odpad.

    Przeszukujemy wszystkie sensowne kombinacje (n6, n3). Zakres jest maly
    (kilkanascie sztuk), wiec przeglad zupelny jest tanszy i pewniejszy
    niz heurystyka.
    """
    dl_max, dl_min = max(dlugosci), min(dlugosci)
    limit_max = math.ceil(dlugosc_m / dl_max) + 1
    limit_min = math.ceil(dlugosc_m / dl_min) + 1

    najlepsza = None
    for n_max in range(limit_max + 1):
        for n_min in range(limit_min + 1):
            suma = n_max * dl_max + n_min * dl_min
            if suma + TOL_M < dlugosc_m or (n_max == 0 and n_min == 0):
                continue
            sztuk = n_max + n_min
            odpad = round(suma - dlugosc_m, 3)
            klucz = (sztuk, odpad)
            if najlepsza is None or klucz < najlepsza[0]:
                najlepsza = (klucz, {dl_max: n_max, dl_min: n_min})

    if najlepsza is None:  # nie powinno wystapic, ale nie zgadujemy
        w = WariantRur(nazwa="mieszany", etykieta="mieszany", mozliwy=False,
                       dlugosc_odcinka_m=round(dlugosc_m, 3),
                       uwaga="Nie udalo sie dobrac kombinacji rur.")
        return w
    return _zbuduj("mieszany", "mieszany (najmniej sztuk)", dlugosc_m, najlepsza[1])


def przelicz(dlugosc_m: float | None,
             dn_profilowe: int | None = None,
             dlugosci: tuple[float, ...] = DLUGOSCI_HANDLOWE_M) -> dict:
    """Policz wszystkie trzy warianty dla odcinka.

    Zwraca slownik gotowy do podania do szablonu albo do API.
    """
    dn_od = srednica_katalogowa(dn_profilowe)
    wynik = {
        "dlugosc_m": round(dlugosc_m, 3) if dlugosc_m else None,
        "dn_profilowe": dn_profilowe,
        "dn_katalogowe": dn_od,
        "dlugosci_handlowe": list(dlugosci),
        "warianty": [],
        "zalecany": None,
        "uwaga": None,
    }
    if not dlugosc_m or dlugosc_m <= 0:
        wynik["uwaga"] = "Odcinek nie ma zapisanej dlugosci - nie da sie policzyc rur."
        return wynik

    warianty = [wariant_jednorodny(dlugosc_m, dl) for dl in sorted(dlugosci)]
    mieszany = wariant_mieszany(dlugosc_m, dlugosci)
    warianty.append(mieszany)

    # Gdy odcinek jest krotszy od najkrotszej rury, cala robota to jedna docinka.
    if dlugosc_m < min(dlugosci) - TOL_M:
        wynik["uwaga"] = (
            f"Odcinek {dlugosc_m:g} m jest krotszy niz najkrotsza rura "
            f"({min(dlugosci):g} m) - potrzebna jedna docinka."
        )

    wynik["warianty"] = [w.to_dict() for w in warianty]
    wynik["zalecany"] = mieszany.nazwa
    return wynik


def przelicz_odcinek(odcinek) -> dict:
    """Wygodna nakladka na model Segment."""
    dlugosc = float(odcinek.dlugosc_m) if odcinek.dlugosc_m is not None else None
    return przelicz(dlugosc, odcinek.dn_mm)


def podsumuj(odcinki, wariant: str = "mieszany") -> dict:
    """Zbiorcze zapotrzebowanie dla wielu odcinkow, w rozbiciu na srednice.

    Przydatne przy zamawianiu materialu na caly ciag albo cala zlewnie.
    """
    wg_srednicy: dict[int, dict] = {}
    bez_danych = []
    for o in odcinki:
        if not o.dlugosc_m or not o.dn_mm:
            bez_danych.append(getattr(o, "nazwa", "?"))
            continue
        dane = przelicz(float(o.dlugosc_m), o.dn_mm)
        w = next(x for x in dane["warianty"] if x["nazwa"] == wariant)
        wpis = wg_srednicy.setdefault(dane["dn_katalogowe"], {
            "dn_katalogowe": dane["dn_katalogowe"],
            "dn_profilowe": dane["dn_profilowe"],
            "dlugosc_m": 0.0, "material_m": 0.0, "odpad_m": 0.0,
            "liczba_ciec": 0, "sztuki": {},
        })
        wpis["dlugosc_m"] = round(wpis["dlugosc_m"] + w["dlugosc_odcinka_m"], 2)
        wpis["material_m"] = round(wpis["material_m"] + w["material_m"], 2)
        wpis["odpad_m"] = round(wpis["odpad_m"] + w["odpad_m"], 2)
        wpis["liczba_ciec"] += w["liczba_ciec"]
        for p in w["pozycje"]:
            wpis["sztuki"][p["dlugosc_m"]] = wpis["sztuki"].get(p["dlugosc_m"], 0) + p["sztuk"]

    return {
        "wariant": wariant,
        "srednice": sorted(wg_srednicy.values(), key=lambda w: w["dn_katalogowe"]),
        "odcinki_bez_danych": bez_danych,
    }
