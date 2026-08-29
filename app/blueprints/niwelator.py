"""Kalkulator niwelacyjny - to, po co brygadzista siega najczesciej."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import select

from app.extensions import db
from app.models import NetworkObject, SurveyPoint
from app.models import Segment
from app.services.leveling import (
    CiagNiwelacyjny,
    przykrycie,
    rzedna_posrednia,
    spadek_z_rzednych,
    wytycz,
)

niwelator_bp = Blueprint("niwelator", __name__)


@niwelator_bp.get("/")
def widok():
    repery = list(db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.aktywny.is_(True)).order_by(SurveyPoint.nazwa)
    ))
    return render_template("pages/niwelator.html", repery=repery)


@niwelator_bp.post("/oblicz")
def oblicz():
    """Wejscie: reper (nazwa albo rzedna), odczyt wstecz, cel (obiekt albo rzedna)."""
    dane = request.get_json(silent=True) or request.form.to_dict()

    rzedna_repera = _liczba(dane.get("rzedna_repera"))
    nazwa_repera = (dane.get("reper") or "").strip()
    if rzedna_repera is None and nazwa_repera:
        punkt = db.session.scalar(select(SurveyPoint).where(SurveyPoint.nazwa == nazwa_repera))
        if punkt is None or punkt.h is None:
            return jsonify({"blad": f"Nie znam rzednej repera {nazwa_repera}"}), 400
        rzedna_repera = float(punkt.h)
    if rzedna_repera is None:
        return jsonify({"blad": "Podaj reper albo jego rzedna."}), 400

    odczyt_wstecz = _liczba(dane.get("odczyt_wstecz"))
    if odczyt_wstecz is None:
        return jsonify({"blad": "Podaj odczyt wstecz na reperze."}), 400

    obiekt = None
    rzedna_proj = _liczba(dane.get("rzedna_projektowa"))
    kod = (dane.get("obiekt") or "").strip()
    if rzedna_proj is None and kod:
        obiekt = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
        if obiekt is None:
            return jsonify({"blad": f"Nie ma obiektu {kod}"}), 404
        cel = (dane.get("cel") or "dno_kanalu").lower()
        zrodlo = obiekt.rzedna_dna_studni if cel == "dno_studni" else obiekt.rzedna_dna_kanalu
        if zrodlo is None:
            return jsonify({"blad": f"Obiekt {kod} nie ma zapisanej rzednej ({cel})."}), 400
        rzedna_proj = float(zrodlo)
    if rzedna_proj is None:
        return jsonify({"blad": "Podaj obiekt albo rzedna projektowa."}), 400

    wynik = wytycz(
        rzedna_repera=rzedna_repera,
        odczyt_wstecz=odczyt_wstecz,
        rzedna_projektowa=rzedna_proj,
        odczyt_zmierzony=_liczba(dane.get("odczyt_zmierzony")),
        tolerancja_m=_liczba(dane.get("tolerancja")) or 0.01,
        reper=nazwa_repera or "reper",
    ).to_dict()

    wynik["reper"] = nazwa_repera or None
    wynik["rzedna_repera"] = rzedna_repera
    wynik["odczyt_wstecz"] = odczyt_wstecz
    if obiekt is not None:
        wynik["obiekt"] = obiekt.to_dict()
        if obiekt.rzedna_terenu_proj is not None:
            wynik["glebokosc_wykopu"] = obiekt.glebokosc_wykopu
            if obiekt.dn_mm:
                wynik["przykrycie"] = przykrycie(
                    float(obiekt.rzedna_terenu_proj), rzedna_proj, obiekt.dn_mm
                )
    return jsonify(wynik)


@niwelator_bp.post("/rzedna-posrednia")
def posrednia():
    """Rzedna dna w dowolnym punkcie odcinka - do tyczenia miedzy studniami."""
    d = request.get_json(silent=True) or request.form.to_dict()
    rz = _liczba(d.get("rzedna_poczatkowa"))
    spadek = _liczba(d.get("spadek_promile"))
    odl = _liczba(d.get("odleglosc_m"))
    if None in (rz, spadek, odl):
        return jsonify({"blad": "Wymagane: rzedna_poczatkowa, spadek_promile, odleglosc_m"}), 400
    return jsonify({
        "rzedna_poczatkowa": rz, "spadek_promile": spadek, "odleglosc_m": odl,
        "rzedna": rzedna_posrednia(rz, spadek, odl),
    })


@niwelator_bp.post("/ciag")
def ciag():
    """Kontrola ciagu niwelacyjnego: suma przewyzszen vs odchylka dopuszczalna."""
    d = request.get_json(silent=True) or {}
    stanowiska = [
        (float(s.get("wstecz", 0)), float(s.get("wprzod", 0)))
        for s in d.get("stanowiska", [])
    ]
    c = CiagNiwelacyjny(
        stanowiska=stanowiska,
        rzedna_poczatkowa=float(d.get("rzedna_poczatkowa", 0)),
        rzedna_koncowa_dana=_liczba(d.get("rzedna_koncowa_dana")),
        dlugosc_km=float(d.get("dlugosc_km", 0)),
    )
    return jsonify(c.to_dict())


@niwelator_bp.get("/spadek")
def spadek():
    a = _liczba(request.args.get("rzedna_od"))
    b = _liczba(request.args.get("rzedna_do"))
    dl = _liczba(request.args.get("dlugosc_m"))
    if None in (a, b, dl):
        return jsonify({"blad": "Wymagane: rzedna_od, rzedna_do, dlugosc_m"}), 400
    promile = spadek_z_rzednych(a, b, dl)
    return jsonify({
        "spadek_promile": promile,
        "spadek_procent": round(promile / 10, 4) if promile is not None else None,
    })


def _liczba(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


# --------------------------------------------------------------- ciag rur


@niwelator_bp.get("/ciag-rur")
def ciag_rur():
    """Formularz tyczenia calego ciagu rur - to, co widzi osoba przy niwelatorze."""
    repery = list(db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.aktywny.is_(True)).order_by(SurveyPoint.nazwa)
    ))
    return render_template("pages/spadek_ciagu.html", repery=repery,
                           od=request.args.get("od", ""), do=request.args.get("do", ""))


@niwelator_bp.post("/ciag-rur/oblicz")
def ciag_rur_oblicz():
    """Policz tyczenie ciagu od obiektu `od` do obiektu `do`."""
    from app.services.spadek_ciagu import TRYB_OS, TRYB_SCIANA, podpowiedz_karb_m, policz_ciag

    d = request.get_json(silent=True) or request.form.to_dict()
    od = (d.get("od") or "").strip()
    do = (d.get("do") or "").strip()
    if not od:
        return jsonify({"blad": "Podaj obiekt początkowy."}), 400

    segmenty = _znajdz_ciag(od, do)
    if not segmenty:
        return jsonify({"blad": f"Nie znalazłem ciągu rur zaczynającego się od {od}."}), 404

    hi = _liczba(d.get("hi"))
    rzedna_repera = _liczba(d.get("rzedna_repera"))
    nazwa_repera = (d.get("reper") or "").strip()
    if hi is None and rzedna_repera is None and nazwa_repera:
        punkt = db.session.scalar(select(SurveyPoint).where(SurveyPoint.nazwa == nazwa_repera))
        if punkt is None or punkt.h is None:
            return jsonify({"blad": f"Nie znam rzednej repera {nazwa_repera}."}), 400
        rzedna_repera = float(punkt.h)

    odczyt_wstecz = _liczba(d.get("odczyt_wstecz"))
    if hi is None and (rzedna_repera is None or odczyt_wstecz is None):
        return jsonify({"blad": "Podaj HI albo reper i odczyt wstecz."}), 400

    pierwszy = segmenty[0]
    rzedna_startowa = _liczba(d.get("rzedna_dna_start"))
    if rzedna_startowa is None:
        if pierwszy.rzedna_dna_od is None:
            return jsonify({"blad": "Podaj zmierzona rzedna dna kanalu na poczatku."}), 400
        rzedna_startowa = float(pierwszy.rzedna_dna_od)

    h_karb = _liczba(d.get("h_karb"))
    if h_karb is None:
        h_karb = podpowiedz_karb_m(pierwszy.dn_mm) or 0.0

    tryb = (d.get("tryb") or TRYB_SCIANA).upper()
    if tryb not in (TRYB_SCIANA, TRYB_OS):
        tryb = TRYB_SCIANA

    wynik = policz_ciag(
        segmenty,
        rzedna_startowa=rzedna_startowa,
        h_karb_m=h_karb,
        rzedna_repera=rzedna_repera,
        odczyt_wstecz=odczyt_wstecz,
        hi=hi,
        tryb=tryb,
        krok_m=_liczba(d.get("krok")) or 3.0,
    )
    wynik["reper"] = nazwa_repera or None
    wynik["podpowiedz_karb_m"] = podpowiedz_karb_m(pierwszy.dn_mm)
    return jsonify(wynik)


def _znajdz_ciag(od: str, do: str = "", limit: int = 40) -> list:
    """Przejdz siec od obiektu `od` w dol, az do `do` albo do konca ciagu."""
    from sqlalchemy.orm import aliased, selectinload

    def wyjscia(kod: str):
        a = aliased(NetworkObject)
        return list(db.session.scalars(
            select(Segment).join(a, Segment.obiekt_od_id == a.id).where(a.kod == kod)
            .options(selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do))
            .order_by(Segment.kolejnosc)
        ))

    segmenty, biezacy, odwiedzone = [], od, {od}
    while len(segmenty) < limit:
        nastepne = wyjscia(biezacy)
        if not nastepne:
            break
        seg = nastepne[0]
        segmenty.append(seg)
        biezacy = seg.obiekt_do.kod
        if biezacy in odwiedzone:      # zabezpieczenie przed petla w danych
            break
        odwiedzone.add(biezacy)
        if do and biezacy == do:
            break
    return segmenty
