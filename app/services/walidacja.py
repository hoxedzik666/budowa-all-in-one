"""Kontrola jakosci danych wczytanych z dokumentacji.

Zasada: **nie zgadujemy poprawnej wartosci**. Jesli rysunek podaje odcinek
o dlugosci 0,00 m albo spadku 314 promili, to znaczy, ze albo tak jest
w dokumentacji, albo parser czegos nie zrozumial. W obu przypadkach jedyna
uczciwa odpowiedzia jest pokazanie tego czlowiekowi z podanym powodem -
brygadzista wchodzacy w wykop musi wiedziec, ze akurat tej liczbie nie wolno
ufac.

Modul dziala na bazie, ale bez Flaska - da sie go wywolac z importu, z komendy
CLI i z testu.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.extensions import db
from app.models import NetworkObject, Segment, TypObiektu

# --- progi ---------------------------------------------------------------

TOL_NIEZMIENNIKA_M = 0.02      # zaglebienie = teren proj. - dno kanalu
MIN_DLUGOSC_M = 0.05           # ponizej tego odcinek nie istnieje fizycznie
MAX_SPADEK_PROMILE = 200.0     # 20% - poza zakresem kanalizacji grawitacyjnej
MAX_DLUGOSC_M = 300.0          # dluzszy odcinek bez studni nie ma prawa wystapic

# Rozjazd spadku rysunkowego i policzonego z rzednych. Na krotkich odcinkach
# to prawie zawsze zaokraglenie: rzedne sa z dokladnoscia 0,01 m, wiec na 3 m
# blad 0,01 m daje juz 3,3 promila. Dlatego prog jest procentowy, z podloga.
TOL_ROZJAZDU_PROMILE = 5.0
TOL_ROZJAZDU_UDZIAL = 0.15


@dataclass
class Problem:
    kategoria: str
    czego_dotyczy: str
    opis: str
    dane: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kategoria": self.kategoria, "dotyczy": self.czego_dotyczy,
                "opis": self.opis, **self.dane}


@dataclass
class RaportJakosci:
    problemy: list[Problem] = field(default_factory=list)
    statystyki: dict = field(default_factory=dict)

    @property
    def wg_kategorii(self) -> dict[str, int]:
        licznik: dict[str, int] = {}
        for p in self.problemy:
            licznik[p.kategoria] = licznik.get(p.kategoria, 0) + 1
        return licznik

    def to_dict(self) -> dict:
        return {"problemy": [p.to_dict() for p in self.problemy],
                "wg_kategorii": self.wg_kategorii,
                "statystyki": self.statystyki}


# --- pojedyncze reguly ---------------------------------------------------


def _sprawdz_odcinek(odc: Segment, nazwa: str) -> list[Problem]:
    """Czy z tego odcinka da sie w ogole wykonac robote."""
    problemy: list[Problem] = []
    dlugosc = float(odc.dlugosc_m) if odc.dlugosc_m is not None else None
    spadek = float(odc.spadek_promile) if odc.spadek_promile is not None else None

    if dlugosc is None:
        problemy.append(Problem(
            "ODCINEK_BEZ_DLUGOSCI", nazwa,
            "Rysunek nie podaje dlugosci - nie da sie policzyc rur ani spadku.",
        ))
    elif dlugosc < MIN_DLUGOSC_M:
        problemy.append(Problem(
            "ODCINEK_ZEROWY", nazwa,
            f"Dlugosc {dlugosc:.2f} m - odcinek o zerowej dlugosci nie istnieje.",
            {"dlugosc_m": dlugosc},
        ))
    elif dlugosc > MAX_DLUGOSC_M:
        problemy.append(Problem(
            "ODCINEK_ZA_DLUGI", nazwa,
            f"Dlugosc {dlugosc:.2f} m przekracza {MAX_DLUGOSC_M:.0f} m - "
            "prawdopodobnie zlaczono dwa odcinki.",
            {"dlugosc_m": dlugosc},
        ))

    if spadek is not None and abs(spadek) > MAX_SPADEK_PROMILE:
        problemy.append(Problem(
            "SPADEK_POZA_ZAKRESEM", nazwa,
            f"Spadek {abs(spadek):.1f} promila ({abs(spadek) / 10:.1f}%) - "
            "poza zakresem kanalizacji grawitacyjnej.",
            {"spadek_promile": spadek, "dlugosc_m": dlugosc},
        ))

    rozjazd = odc.rozjazd_spadku_promile
    if rozjazd is not None and spadek is not None:
        prog = max(TOL_ROZJAZDU_PROMILE, abs(spadek) * TOL_ROZJAZDU_UDZIAL)
        if rozjazd > prog:
            problemy.append(Problem(
                "ROZJAZD_SPADKU", nazwa,
                f"Spadek z rysunku {abs(spadek):.1f} promila, a z rzednych "
                f"{odc.spadek_wyliczony_promile:.1f} promila (roznica {rozjazd:.1f}).",
                {"spadek_rysunek": abs(spadek),
                 "spadek_z_rzednych": odc.spadek_wyliczony_promile,
                 "dlugosc_m": dlugosc},
            ))
    return problemy


def _sprawdz_obiekt(ob: NetworkObject) -> list[Problem]:
    """Niezmiennik rzednych - jedyna reguła, ktora trzyma dane w ryzach."""
    if ob.rzedna_terenu_proj is None or ob.rzedna_dna_kanalu is None:
        return []
    if ob.zaglebienie is None:
        return []
    oczekiwane = float(ob.rzedna_terenu_proj) - float(ob.rzedna_dna_kanalu)
    roznica = abs(oczekiwane - float(ob.zaglebienie))
    if roznica <= TOL_NIEZMIENNIKA_M:
        return []
    return [Problem(
        "NIEZMIENNIK_RZEDNYCH", ob.kod,
        f"Zaglebienie {float(ob.zaglebienie):.2f} m, a z rzednych wychodzi "
        f"{oczekiwane:.2f} m (roznica {roznica:.2f} m).",
        {"teren_proj": float(ob.rzedna_terenu_proj),
         "dno_kanalu": float(ob.rzedna_dna_kanalu),
         "zaglebienie": float(ob.zaglebienie)},
    )]


# --- calosc --------------------------------------------------------------

# Kategorie, ktore dyskwalifikuja odcinek do liczenia rur i tyczenia.
KATEGORIE_BLOKUJACE = {
    "ODCINEK_BEZ_DLUGOSCI", "ODCINEK_ZEROWY", "ODCINEK_ZA_DLUGI",
    "SPADEK_POZA_ZAKRESEM",
}


def sprawdz_dane(oznacz: bool = True) -> RaportJakosci:
    """Przejrzyj cala baze i zbierz to, co sie nie trzyma kupy.

    `oznacz=True` zapisuje flage `podejrzany` na odcinkach z powaznym bledem,
    zeby widoki mogly ostrzec, zanim ktos policzy z nich material.
    """
    raport = RaportJakosci()

    a, b = aliased(NetworkObject), aliased(NetworkObject)
    odcinki = db.session.execute(
        select(Segment, a.kod, b.kod)
        .join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
    ).all()

    powody: dict[int, list[str]] = {}
    for odc, kod_od, kod_do in odcinki:
        nazwa = f"{kod_od}-{kod_do}"
        for problem in _sprawdz_odcinek(odc, nazwa):
            raport.problemy.append(problem)
            if problem.kategoria in KATEGORIE_BLOKUJACE:
                powody.setdefault(odc.id, []).append(problem.opis)

    if oznacz:
        for odc, _, _ in odcinki:
            nowe = powody.get(odc.id)
            odc.podejrzany = bool(nowe)
            odc.powod_podejrzenia = " ".join(nowe) if nowe else None
        db.session.commit()

    for ob in db.session.scalars(select(NetworkObject)):
        raport.problemy.extend(_sprawdz_obiekt(ob))

    raport.statystyki = _statystyki(len(odcinki), len(powody))
    return raport


def _statystyki(odcinkow: int, podejrzanych: int) -> dict:
    """Braki w danych - nie bledy, ale kierownik ma prawo wiedziec."""
    def ile(model, *warunki) -> int:
        return db.session.scalar(
            select(func.count()).select_from(model).where(*warunki)
        ) or 0

    obiektow = ile(NetworkObject)
    bez_odcinka = ile(
        NetworkObject,
        ~NetworkObject.id.in_(select(Segment.obiekt_od_id)),
        ~NetworkObject.id.in_(select(Segment.obiekt_do_id)),
    )

    return {
        "odcinkow": odcinkow,
        "odcinkow_podejrzanych": podejrzanych,
        "odcinkow_bez_dn": ile(Segment, Segment.dn_mm.is_(None)),
        "odcinkow_bez_spadku": ile(Segment, Segment.spadek_promile.is_(None)),
        "obiektow": obiektow,
        "obiektow_bez_odcinka": bez_odcinka,
        "obiektow_bez_dna": ile(NetworkObject, NetworkObject.rzedna_dna_kanalu.is_(None)),
        "studni_bez_srednicy": ile(
            NetworkObject,
            NetworkObject.typ == TypObiektu.STUDNIA,
            NetworkObject.srednica_studni_mm.is_(None),
        ),
    }
