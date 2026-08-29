"""Spadek na ciagu rur - to, co ma zobaczyc osoba przy niwelatorze.

Problem z budowy
----------------
Monter nie postawi laty na cieku rury, bo rura mu w tym przeszkadza. Stawia ja
na **gornym karbie**. Miedzy ciekiem a karbem jest stala roznica `h_karb`,
ktora trzeba doliczyc, zanim poda sie odczyt osobie przy niwelatorze:

    rzedna laty = rzedna dna + h_karb
    ODCZYT      = HI - rzedna laty

Dlugosc rury a dlugosc z profilu
--------------------------------
Profil podaje odleglosc **os-os studni**. Rura fizycznie biegnie od sciany do
sciany, czyli jest krotsza o promienie obu studni:

    L_rura = L_os - (DN_studni_od + DN_studni_do) / 2

Co z tego wynika dla spadku - zalezy od tego, do czego odnosza sie rzedne
z dokumentacji, a to bywa rozne u roznych projektantow. Liczymy **oba warianty**
i pozwalamy przelaczyc:

    SCIANA - cala projektowa roznica rzednych musi sie zmiescic na dlugosci
             rury:            i = dh / L_rura    (spadek STROMSZY)
    OS     - spadek obowiazuje na calej osi, rura zajmuje srodek:
                              i = dh / L_os      (spadek bez zmian)

Przy 20,5 m miedzy studniami DN1500 i dh = 0,06 m roznica jest niewielka
(3,16 vs 3,00 promila), ale przy 90 promilach siega 7% - a na krotkim
przykanaliku to juz centymetry w wykopie.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import TypObiektu
from app.services.leveling import DLUGOSC_LATY_M, Stanowisko

# Tryby interpretacji rzednych z dokumentacji.
TRYB_SCIANA = "SCIANA"
TRYB_OS = "OS"

# Typy koncow, ktore realnie maja srednice do odjecia. Wpust to nie studnia,
# a wylot to po prostu koniec rury - przy nich nie odejmujemy niczego.
TYPY_ZE_SREDNICA = (
    TypObiektu.STUDNIA,
    TypObiektu.SEPARATOR,
    TypObiektu.OSADNIK,
)


def promien_konca(obiekt, nadpisanie_mm: float | None = None) -> float:
    """Ile metrow odjac z dlugosci osiowej po tej stronie odcinka."""
    if nadpisanie_mm is not None:
        return max(float(nadpisanie_mm), 0.0) / 2000.0
    if obiekt is None or obiekt.typ not in TYPY_ZE_SREDNICA:
        return 0.0
    if obiekt.srednica_studni_mm is None:
        return 0.0
    return float(obiekt.srednica_studni_mm) / 2000.0


@dataclass
class PunktTyczenia:
    """Jedno miejsce, w ktorym monter stawia late."""

    odleglosc_m: float
    rzedna_dna: float
    rzedna_laty: float
    odczyt: float
    opis: str = ""
    wykonalny: bool = True

    def to_dict(self) -> dict:
        return {
            "odleglosc_m": round(self.odleglosc_m, 2),
            "rzedna_dna": round(self.rzedna_dna, 3),
            "rzedna_laty": round(self.rzedna_laty, 3),
            "odczyt": round(self.odczyt, 3),
            "opis": self.opis,
            "wykonalny": self.wykonalny,
        }


@dataclass
class OdcinekTyczenia:
    """Wynik dla jednego odcinka ciagu."""

    nazwa: str
    od: str
    do: str
    dlugosc_osiowa_m: float
    dlugosc_rury_m: float
    promien_od_m: float
    promien_do_m: float
    dn_mm: int | None
    roznica_rzednych_m: float
    spadek_projektowy_promile: float | None
    spadek_sciana_promile: float | None
    spadek_os_promile: float | None
    rzedna_start: float
    rzedna_koniec: float
    punkty: list[PunktTyczenia] = field(default_factory=list)
    uwagi: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nazwa": self.nazwa, "od": self.od, "do": self.do,
            "dlugosc_osiowa_m": round(self.dlugosc_osiowa_m, 2),
            "dlugosc_rury_m": round(self.dlugosc_rury_m, 2),
            "promien_od_m": round(self.promien_od_m, 3),
            "promien_do_m": round(self.promien_do_m, 3),
            "dn_mm": self.dn_mm,
            "roznica_rzednych_m": round(self.roznica_rzednych_m, 3),
            "spadek_projektowy_promile": self.spadek_projektowy_promile,
            "spadek_sciana_promile": self.spadek_sciana_promile,
            "spadek_os_promile": self.spadek_os_promile,
            "rzedna_start": round(self.rzedna_start, 3),
            "rzedna_koniec": round(self.rzedna_koniec, 3),
            "punkty": [p.to_dict() for p in self.punkty],
            "uwagi": self.uwagi,
        }


def _kroki(dlugosc: float, krok: float) -> list[float]:
    """Odleglosci, w ktorych stawiamy late: co `krok`, zawsze z koncem odcinka."""
    if krok <= 0:
        return [0.0, dlugosc]
    punkty, x = [], 0.0
    while x < dlugosc - 1e-6:
        punkty.append(round(x, 3))
        x += krok
    punkty.append(round(dlugosc, 3))
    return punkty


def policz_odcinek(
    segment,
    rzedna_startowa: float,
    h_karb_m: float,
    hi: float,
    tryb: str = TRYB_SCIANA,
    krok_m: float = 3.0,
    srednica_od_mm: float | None = None,
    srednica_do_mm: float | None = None,
) -> OdcinekTyczenia:
    """Policz tyczenie jednego odcinka, zaczynajac od zmierzonej rzednej dna."""
    dlugosc_os = float(segment.dlugosc_m or 0)
    r_od = promien_konca(segment.obiekt_od, srednica_od_mm)
    r_do = promien_konca(segment.obiekt_do, srednica_do_mm)
    dlugosc_rury = max(dlugosc_os - r_od - r_do, 0.0)

    uwagi: list[str] = []
    if dlugosc_os <= 0:
        uwagi.append("Odcinek nie ma zapisanej długości — nie da się policzyć tyczenia.")
    if dlugosc_rury <= 0 and dlugosc_os > 0:
        uwagi.append(
            "Po odjęciu średnic studni długość rury wychodzi zerowa — sprawdź wymiary studni."
        )

    # Roznica rzednych z dokumentacji; bierzemy wartosc bezwzgledna, bo profile
    # rysuje sie od wylotu w gore zlewni i znak bywa odwrotny do kierunku splywu.
    if segment.rzedna_dna_od is not None and segment.rzedna_dna_do is not None:
        dh = abs(float(segment.rzedna_dna_od) - float(segment.rzedna_dna_do))
    elif segment.spadek_promile and dlugosc_os:
        dh = abs(float(segment.spadek_promile)) / 1000.0 * dlugosc_os
        uwagi.append("Brak rzędnych w bazie — różnicę policzono ze spadku projektowego.")
    else:
        dh = 0.0
        uwagi.append("Brak rzędnych i spadku — przyjęto zerową różnicę.")

    spadek_sciana = round(dh / dlugosc_rury * 1000, 3) if dlugosc_rury > 0 else None
    spadek_os = round(dh / dlugosc_os * 1000, 3) if dlugosc_os > 0 else None
    spadek = spadek_sciana if tryb == TRYB_SCIANA else spadek_os
    if spadek is None:
        spadek = 0.0

    punkty = []
    for x in _kroki(dlugosc_rury, krok_m):
        rzedna_dna = rzedna_startowa - spadek / 1000.0 * x
        rzedna_laty = rzedna_dna + h_karb_m
        odczyt = hi - rzedna_laty
        opis = ""
        if x == 0:
            opis = f"początek — {segment.obiekt_od.kod if segment.obiekt_od else 'start'}"
        elif abs(x - dlugosc_rury) < 1e-6:
            opis = f"koniec — {segment.obiekt_do.kod if segment.obiekt_do else 'koniec'}"
        punkty.append(PunktTyczenia(
            odleglosc_m=x, rzedna_dna=rzedna_dna, rzedna_laty=rzedna_laty,
            odczyt=odczyt, opis=opis,
            wykonalny=0.0 <= odczyt <= DLUGOSC_LATY_M,
        ))

    niewykonalne = [p for p in punkty if not p.wykonalny]
    if niewykonalne:
        uwagi.append(
            f"{len(niewykonalne)} z {len(punkty)} odczytów wypada poza łatą "
            f"(0–{DLUGOSC_LATY_M:.0f} m) — potrzebne stanowisko pośrednie."
        )

    return OdcinekTyczenia(
        nazwa=segment.nazwa,
        od=segment.obiekt_od.kod if segment.obiekt_od else "?",
        do=segment.obiekt_do.kod if segment.obiekt_do else "?",
        dlugosc_osiowa_m=dlugosc_os,
        dlugosc_rury_m=dlugosc_rury,
        promien_od_m=r_od,
        promien_do_m=r_do,
        dn_mm=segment.dn_mm,
        roznica_rzednych_m=dh,
        spadek_projektowy_promile=(
            float(segment.spadek_promile) if segment.spadek_promile is not None else None
        ),
        spadek_sciana_promile=spadek_sciana,
        spadek_os_promile=spadek_os,
        rzedna_start=rzedna_startowa,
        rzedna_koniec=punkty[-1].rzedna_dna if punkty else rzedna_startowa,
        punkty=punkty,
        uwagi=uwagi,
    )


def policz_ciag(
    segmenty: list,
    rzedna_startowa: float,
    h_karb_m: float,
    rzedna_repera: float | None = None,
    odczyt_wstecz: float | None = None,
    hi: float | None = None,
    tryb: str = TRYB_SCIANA,
    krok_m: float = 3.0,
    nadpisania: dict | None = None,
) -> dict:
    """Policz tyczenie calego ciagu odcinkow, jeden po drugim.

    Rzedna konca jednego odcinka jest rzedna poczatku nastepnego - dzieki temu
    calkowity spadek na ciagu wynika z rzeczywistych dlugosci rur, a nie
    z sumy dlugosci osiowych.
    """
    if hi is None:
        if rzedna_repera is None or odczyt_wstecz is None:
            return {"blad": "Podaj wysokość celowej (HI) albo reper i odczyt wstecz."}
        hi = Stanowisko(reper="reper", rzedna_repera=rzedna_repera,
                        odczyt_wstecz=odczyt_wstecz).hi

    nadpisania = nadpisania or {}
    wyniki, rzedna = [], rzedna_startowa
    for i, seg in enumerate(segmenty):
        wynik = policz_odcinek(
            seg, rzedna_startowa=rzedna, h_karb_m=h_karb_m, hi=hi, tryb=tryb, krok_m=krok_m,
            srednica_od_mm=nadpisania.get(f"{i}_od"),
            srednica_do_mm=nadpisania.get(f"{i}_do"),
        )
        wyniki.append(wynik)
        rzedna = wynik.rzedna_koniec

    dlugosc_os = sum(w.dlugosc_osiowa_m for w in wyniki)
    dlugosc_rury = sum(w.dlugosc_rury_m for w in wyniki)
    spadek_calkowity = rzedna_startowa - rzedna

    return {
        "hi": round(hi, 4),
        "tryb": tryb,
        "h_karb_m": h_karb_m,
        "krok_m": krok_m,
        "rzedna_startowa": round(rzedna_startowa, 3),
        "rzedna_koncowa": round(rzedna, 3),
        "spadek_calkowity_m": round(spadek_calkowity, 3),
        "dlugosc_osiowa_m": round(dlugosc_os, 2),
        "dlugosc_rury_m": round(dlugosc_rury, 2),
        "sredni_spadek_promile": (
            round(spadek_calkowity / dlugosc_rury * 1000, 2) if dlugosc_rury > 0 else None
        ),
        "odcinki": [w.to_dict() for w in wyniki],
        "uwagi": [u for w in wyniki for u in w.uwagi],
    }


def podpowiedz_karb_m(dn_mm: int | None) -> float | None:
    """Podpowiedz wysokosci od cieku do gornego karba.

    Dla rur karbowanych (PRAGMA) gorny karb lezy mniej wiecej na wysokosci
    srednicy zewnetrznej. To tylko punkt wyjscia - monter i tak podaje wymiar
    zmierzony na budowie, bo zalezy od producenta i serii.
    """
    from app.services.rury import srednica_katalogowa

    od = srednica_katalogowa(dn_mm)
    return round(od / 1000.0, 3) if od else None
