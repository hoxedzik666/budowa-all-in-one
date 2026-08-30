"""Postep robot: stan odcinkow i raporty dzienne brygady.

Dwa widoki, jedna sprawa. `/postep` odpowiada na pytanie kierownika - **ile
zrobione**. `/raporty` odpowiada na pytanie z konca dnia - **co dzis zrobiono**.
"""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased, selectinload

from app.extensions import db
from app.models import (
    ETYKIETY,
    KLASY_PLAKIETKI,
    SCIEZKA,
    STANY_GOTOWE,
    NetworkObject,
    PomiarWykonawczy,
    RaportDzienny,
    Segment,
    StatusWykonania,
    ZmianaStatusu,
    nastepny_stan,
    poprzedni_stan,
    wolno_ustawic,
)
from app.services.powiazania import powiaz

postep_bp = Blueprint("postep", __name__)

LIMIT_LISTY = 300
DNI_PODSUMOWANIA = 7


# ---------------------------------------------------------------- odcinki


def historia(odcinek: Segment) -> list[ZmianaStatusu]:
    return list(db.session.scalars(
        select(ZmianaStatusu)
        .where(ZmianaStatusu.segment_id == odcinek.id)
        .options(selectinload(ZmianaStatusu.autor))
        .order_by(ZmianaStatusu.utworzono.desc())
    ))


def ostrzezenia_przed_zgloszeniem(odcinek: Segment, nowy: StatusWykonania) -> list[str]:
    """Co powinno zapalic lampke, zanim ktos zglosi odcinek jako zrobiony.

    Nie blokujemy - na budowie zdarza sie zglosic odcinek przed wpisaniem
    pomiarow. Ale jesli pomiary juz sa i cos w nich nie gra, trzeba to
    powiedziec **z liczba**, a nie ogolnikiem.
    """
    if nowy not in STANY_GOTOWE:
        return []

    from app.blueprints.wykonanie import podsumowanie_odcinka

    uwagi: list[str] = []
    podsumowanie = podsumowanie_odcinka(odcinek)

    if podsumowanie is None:
        uwagi.append("Ten odcinek nie ma ani jednego pomiaru wykonawczego — "
                     "nie ma czym potwierdzić wykonania.")
        return uwagi

    if podsumowanie["poza_tolerancja"]:
        najwieksza = podsumowanie["najwieksza_odchylka_m"]
        uwagi.append(
            f"{podsumowanie['poza_tolerancja']} z {podsumowanie['pomiarow']} pomiarów "
            f"jest poza tolerancją, największa odchyłka {najwieksza:.3f} m."
        )

    spadek = podsumowanie.get("spadek")
    if spadek and spadek.get("poprawny_kierunek") is False:
        uwagi.append(
            f"Spadek wyszedł w złą stronę — woda popłynie pod górę "
            f"({spadek['spadek_promile']:.1f}‰ na {spadek['dlugosc_m']:.1f} m)."
        )
    if odcinek.podejrzany:
        uwagi.append(f"Dane odcinka są oznaczone jako niepewne: {odcinek.powod_podejrzenia}")

    return uwagi


def statystyki_postepu() -> dict:
    """Metry i sztuki w kazdym stanie - podstawa procentu wykonania sieci."""
    wiersze = db.session.execute(
        select(Segment.status, func.count(), func.sum(Segment.dlugosc_m))
        .group_by(Segment.status)
    ).all()

    wg_stanu = {
        stan: {"sztuk": 0, "metry": 0.0, "etykieta": ETYKIETY[stan],
               "klasa": KLASY_PLAKIETKI[stan]}
        for stan in SCIEZKA
    }
    for stan, sztuk, metry in wiersze:
        wg_stanu[stan]["sztuk"] = sztuk
        wg_stanu[stan]["metry"] = round(float(metry or 0), 1)

    razem_m = sum(w["metry"] for w in wg_stanu.values())
    gotowe_m = sum(wg_stanu[s]["metry"] for s in STANY_GOTOWE)
    odebrane_m = wg_stanu[StatusWykonania.ODEBRANY]["metry"]

    return {
        "wg_stanu": wg_stanu,
        "razem_m": round(razem_m, 1),
        "gotowe_m": round(gotowe_m, 1),
        "odebrane_m": round(odebrane_m, 1),
        "procent_gotowe": round(gotowe_m / razem_m * 100, 1) if razem_m else 0.0,
        "procent_odebrane": round(odebrane_m / razem_m * 100, 1) if razem_m else 0.0,
    }


@postep_bp.get("/postep")
@login_required
def przeglad():
    wybrany = request.args.get("stan", "")
    szukaj = (request.args.get("szukaj") or "").strip()

    a, b = aliased(NetworkObject), aliased(NetworkObject)
    q = (
        select(Segment)
        .join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
        .options(selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do),
                 selectinload(Segment.profil))
    )
    if wybrany in StatusWykonania.__members__:
        q = q.where(Segment.status == StatusWykonania[wybrany])
    else:
        # Domyslnie pokazujemy to, co sie dzieje - a nie 649 odcinkow w projekcie.
        q = q.where(Segment.status != StatusWykonania.PROJEKT)
    if szukaj:
        q = q.where(or_(a.kod.ilike(f"%{szukaj}%"), b.kod.ilike(f"%{szukaj}%")))

    odcinki = list(db.session.scalars(q.order_by(a.kod).limit(LIMIT_LISTY)))

    # Ostatnia zmiana kazdego z wypisanych odcinkow - kto i kiedy.
    ostatnie: dict[int, ZmianaStatusu] = {}
    if odcinki:
        for zmiana in db.session.scalars(
            select(ZmianaStatusu)
            .where(ZmianaStatusu.segment_id.in_([o.id for o in odcinki]))
            .options(selectinload(ZmianaStatusu.autor))
            .order_by(ZmianaStatusu.utworzono)
        ):
            ostatnie[zmiana.segment_id] = zmiana

    return render_template(
        "pages/postep.html",
        odcinki=odcinki, ostatnie=ostatnie, wybrany=wybrany, szukaj=szukaj,
        stany=list(SCIEZKA), etykiety=ETYKIETY, klasy=KLASY_PLAKIETKI,
        staty=statystyki_postepu(),
    )


@postep_bp.post("/postep/<int:segment_id>/stan")
@login_required
def zmien_stan(segment_id: int):
    odcinek = db.session.get(Segment, segment_id)
    if odcinek is None:
        abort(404, "Nie ma takiego odcinka.")

    nazwa = request.form.get("stan", "")
    if nazwa not in StatusWykonania.__members__:
        abort(400, "Nieznany stan.")
    nowy = StatusWykonania[nazwa]
    obecny = odcinek.status or StatusWykonania.PROJEKT

    wolno, powod = wolno_ustawic(current_user, obecny, nowy)
    if not wolno:
        flash(powod, "warning")
        return redirect(request.referrer or url_for("postep.przeglad"))

    for uwaga in ostrzezenia_przed_zgloszeniem(odcinek, nowy):
        flash(uwaga, "warning")

    db.session.add(ZmianaStatusu(
        segment_id=odcinek.id, poprzedni=obecny, nowy=nowy,
        autor_id=current_user.id,
        uwagi=(request.form.get("uwagi") or "").strip() or None,
    ))
    odcinek.status = nowy
    db.session.commit()

    flash(f"{odcinek.nazwa}: {ETYKIETY[obecny]} → {ETYKIETY[nowy]}.", "success")
    return redirect(request.referrer or url_for("postep.przeglad"))


@postep_bp.get("/api/postep/odcinek/<od>/<do_>")
@login_required
def api_odcinek(od: str, do_: str):
    _, odcinek, blad = powiaz(f"{od}-{do_}")
    if odcinek is None:
        return jsonify({"blad": blad or f"Nie ma odcinka {od}-{do_}."}), 404

    obecny = odcinek.status or StatusWykonania.PROJEKT
    nastepny = nastepny_stan(obecny)
    poprzedni = poprzedni_stan(obecny)

    def opis(stan):
        if stan is None:
            return None
        wolno, powod = wolno_ustawic(current_user, obecny, stan)
        return {"stan": stan.name, "etykieta": ETYKIETY[stan],
                "wolno": wolno, "powod": powod or None}

    return jsonify({
        "odcinek": odcinek.nazwa,
        "stan": obecny.name,
        "etykieta": ETYKIETY[obecny],
        "klasa": KLASY_PLAKIETKI[obecny],
        "nastepny": opis(nastepny),
        "poprzedni": opis(poprzedni),
        "ostrzezenia": ostrzezenia_przed_zgloszeniem(odcinek, StatusWykonania.WYKONANY),
        "historia": [z.to_dict() for z in historia(odcinek)],
    })


# --------------------------------------------------------------- raporty


def raporty_widoczne_dla(uzytkownik):
    """Monter widzi wylacznie swoje wpisy, reszta - calej brygady."""
    q = select(RaportDzienny).options(
        selectinload(RaportDzienny.autor),
        selectinload(RaportDzienny.segment).selectinload(Segment.obiekt_od),
        selectinload(RaportDzienny.segment).selectinload(Segment.obiekt_do),
        selectinload(RaportDzienny.obiekt),
    )
    if not uzytkownik.widzi_cudze_raporty:
        return q.where(RaportDzienny.autor_id == uzytkownik.id)
    return q


def podsumowanie_tygodnia(uzytkownik) -> dict:
    od_dnia = date.today() - timedelta(days=DNI_PODSUMOWANIA - 1)
    q = raporty_widoczne_dla(uzytkownik).where(RaportDzienny.data_raportu >= od_dnia)
    raporty = list(db.session.scalars(q))

    return {
        "od_dnia": od_dnia,
        "wpisow": len(raporty),
        "metry": round(sum(float(r.metry or 0) for r in raporty), 1),
        "dniowki": sum(int(r.ludzi or 0) for r in raporty),
        "przestoje_h": round(sum(float(r.przestoj_godziny or 0) for r in raporty), 1),
        "z_przestojem": sum(1 for r in raporty if r.byl_przestoj),
    }


@postep_bp.get("/raporty")
@login_required
def raporty():
    q = raporty_widoczne_dla(current_user)

    dzien = (request.args.get("dzien") or "").strip()
    if dzien:
        try:
            q = q.where(RaportDzienny.data_raportu == date.fromisoformat(dzien))
        except ValueError:
            flash("Data musi być w formacie RRRR-MM-DD.", "warning")

    szukaj = (request.args.get("szukaj") or "").strip()
    if szukaj:
        a, b = aliased(NetworkObject), aliased(NetworkObject)
        q = (q.join(Segment, RaportDzienny.segment_id == Segment.id)
              .join(a, Segment.obiekt_od_id == a.id)
              .join(b, Segment.obiekt_do_id == b.id)
              .where(or_(a.kod.ilike(f"%{szukaj}%"), b.kod.ilike(f"%{szukaj}%"))))

    lista = list(db.session.scalars(
        q.order_by(RaportDzienny.data_raportu.desc(), RaportDzienny.id.desc())
         .limit(LIMIT_LISTY)
    ))

    return render_template(
        "pages/raporty.html",
        raporty=lista, dzien=dzien, szukaj=szukaj,
        dzisiaj=date.today().isoformat(),
        tydzien=podsumowanie_tygodnia(current_user),
        stany=list(SCIEZKA), etykiety=ETYKIETY,
    )


@postep_bp.post("/raporty/dodaj")
@login_required
def dodaj_raport():
    dotyczy = (request.form.get("dotyczy") or "").strip()
    obiekt = odcinek = None
    if dotyczy:
        obiekt, odcinek, blad = powiaz(dotyczy)
        if blad:
            flash(blad, "danger")
            return redirect(request.referrer or url_for("postep.raporty"))

    opis = (request.form.get("opis") or "").strip()
    if not opis:
        flash("Opis wykonanej pracy jest wymagany — to sedno raportu.", "warning")
        return redirect(request.referrer or url_for("postep.raporty"))

    def liczba(pole: str):
        surowa = (request.form.get(pole) or "").replace(",", ".").strip()
        if not surowa:
            return None
        try:
            return float(surowa)
        except ValueError:
            return None

    raport = RaportDzienny(
        autor_id=current_user.id,
        brygada=(request.form.get("brygada") or "").strip() or None,
        segment_id=odcinek.id if odcinek else None,
        obiekt_id=obiekt.id if (obiekt and odcinek is None) else None,
        opis=opis,
        metry=liczba("metry"),
        ludzi=int(liczba("ludzi")) if liczba("ludzi") is not None else None,
        sprzet=(request.form.get("sprzet") or "").strip() or None,
        pogoda=(request.form.get("pogoda") or "").strip() or None,
        przestoj_godziny=liczba("przestoj_godziny"),
        przestoj_powod=(request.form.get("przestoj_powod") or "").strip() or None,
    )
    data_raportu = (request.form.get("data") or "").strip()
    if data_raportu:
        try:
            raport.data_raportu = date.fromisoformat(data_raportu)
        except ValueError:
            flash("Data musi być w formacie RRRR-MM-DD — zapisuję z dzisiejszą.", "warning")

    db.session.add(raport)

    # Jednym formularzem: raport i zmiana stanu odcinka. To najczestszy ruch
    # konca dnia i nie ma powodu, zeby wymagal dwoch wizyt w aplikacji.
    nowy_stan = request.form.get("stan") or ""
    if odcinek is not None and nowy_stan in StatusWykonania.__members__:
        nowy = StatusWykonania[nowy_stan]
        obecny = odcinek.status or StatusWykonania.PROJEKT
        wolno, powod = wolno_ustawic(current_user, obecny, nowy)
        if not wolno:
            flash(powod, "warning")
        else:
            for uwaga in ostrzezenia_przed_zgloszeniem(odcinek, nowy):
                flash(uwaga, "warning")
            db.session.add(ZmianaStatusu(
                segment_id=odcinek.id, poprzedni=obecny, nowy=nowy,
                autor_id=current_user.id, uwagi=f"z raportu dziennego: {opis[:200]}",
            ))
            odcinek.status = nowy
            flash(f"{odcinek.nazwa}: {ETYKIETY[obecny]} → {ETYKIETY[nowy]}.", "success")

    db.session.commit()
    flash("Raport zapisany.", "success")
    return redirect(request.referrer or url_for("postep.raporty"))


@postep_bp.post("/raporty/<int:raport_id>/usun")
@login_required
def usun_raport(raport_id: int):
    raport = db.session.get(RaportDzienny, raport_id)
    if raport is None:
        flash("Nie ma takiego raportu.", "warning")
        return redirect(url_for("postep.raporty"))

    wlasny = raport.autor_id == current_user.id
    if not (wlasny or current_user.jest_adminem):
        flash("Usunąć raport może jego autor albo administrator.", "danger")
        return redirect(url_for("postep.raporty"))

    db.session.delete(raport)
    db.session.commit()
    flash("Raport usunięty.", "success")
    return redirect(request.referrer or url_for("postep.raporty"))


@postep_bp.get("/api/raporty")
@login_required
def api_raporty():
    lista = list(db.session.scalars(
        raporty_widoczne_dla(current_user)
        .order_by(RaportDzienny.data_raportu.desc())
        .limit(LIMIT_LISTY)
    ))
    tydzien = podsumowanie_tygodnia(current_user)
    tydzien["od_dnia"] = tydzien["od_dnia"].isoformat()
    return jsonify({"raporty": [r.to_dict() for r in lista], "tydzien": tydzien})
