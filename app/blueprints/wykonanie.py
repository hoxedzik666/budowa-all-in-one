"""Dziennik wykonawczy: rzedne zmierzone w wykopie.

Projekt mowi, jak ma byc. Ten widok mowi, jak jest - i o ile te dwie rzeczy
sie roznia. Nic tu nie nadpisuje projektu; kazdy pomiar to osobny wpis
z data i autorem, wiec historia zostaje.
"""
from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

from app.extensions import db
from app.models import (
    NetworkObject,
    PomiarWykonawczy,
    RodzajPomiaru,
    Segment,
    spadek_wykonany,
)

wykonanie_bp = Blueprint("wykonanie", __name__)

LIMIT_LISTY = 300


def _powiaz(fraza: str) -> tuple[NetworkObject | None, Segment | None, str | None]:
    """Zamien wpis `D155` albo `Wyl101-D155` na obiekt albo odcinek.

    Ta sama zasada, co w zadaniach - brygadzista pisze to, co ma na rysunku,
    a nie identyfikator z bazy.
    """
    fraza = (fraza or "").strip()
    if not fraza:
        return None, None, "Podaj obiekt (np. D155) albo odcinek (np. Wyl101-D155)."

    if "-" in fraza:
        od, _, do_ = fraza.partition("-")
        a, b = aliased(NetworkObject), aliased(NetworkObject)
        odcinek = db.session.scalar(
            select(Segment).join(a, Segment.obiekt_od_id == a.id)
            .join(b, Segment.obiekt_do_id == b.id)
            .where(func.lower(a.kod) == od.strip().lower(),
                   func.lower(b.kod) == do_.strip().lower())
        )
        if odcinek is not None:
            return odcinek.obiekt_od, odcinek, None

    obiekt = db.session.scalar(
        select(NetworkObject).where(func.lower(NetworkObject.kod) == fraza.lower())
    )
    if obiekt is not None:
        return obiekt, None, None
    return None, None, f"Nie znam obiektu ani odcinka „{fraza}”."


def pomiary_odcinka(odcinek: Segment) -> list[PomiarWykonawczy]:
    return list(db.session.scalars(
        select(PomiarWykonawczy)
        .where(PomiarWykonawczy.segment_id == odcinek.id)
        .order_by(PomiarWykonawczy.odleglosc_m, PomiarWykonawczy.data_pomiaru)
        .options(selectinload(PomiarWykonawczy.autor))
    ))


def podsumowanie_odcinka(odcinek: Segment) -> dict | None:
    """Wykonanie odcinka: ile punktow, jaki spadek wyszedl, co poza tolerancja."""
    pomiary = pomiary_odcinka(odcinek)
    if not pomiary:
        return None
    poza = [p for p in pomiary if p.w_tolerancji is False]
    return {
        "pomiarow": len(pomiary),
        "poza_tolerancja": len(poza),
        "najwieksza_odchylka_m": max(
            (abs(p.odchylka_m) for p in pomiary if p.odchylka_m is not None), default=None),
        "spadek": spadek_wykonany(pomiary, odcinek),
        "spadek_projektowy_promile": (
            float(odcinek.spadek_promile) if odcinek.spadek_promile is not None else None),
        "pomiary": pomiary,
    }


@wykonanie_bp.get("/wykonanie")
def dziennik():
    zakres = request.args.get("zakres", "wszystkie")
    q = (
        select(PomiarWykonawczy)
        .options(selectinload(PomiarWykonawczy.obiekt),
                 selectinload(PomiarWykonawczy.segment).selectinload(Segment.obiekt_od),
                 selectinload(PomiarWykonawczy.segment).selectinload(Segment.obiekt_do),
                 selectinload(PomiarWykonawczy.autor))
        .order_by(PomiarWykonawczy.data_pomiaru.desc(), PomiarWykonawczy.id.desc())
        .limit(LIMIT_LISTY)
    )
    if zakres == "moje" and current_user.is_authenticated:
        q = q.where(PomiarWykonawczy.autor_id == current_user.id)

    pomiary = list(db.session.scalars(q))
    if zakres == "poza-tolerancja":
        pomiary = [p for p in pomiary if p.w_tolerancji is False]

    return render_template(
        "pages/wykonanie.html",
        pomiary=pomiary,
        zakres=zakres,
        rodzaje=list(RodzajPomiaru),
        dzisiaj=date.today().isoformat(),
        liczby={
            "razem": db.session.scalar(
                select(func.count()).select_from(PomiarWykonawczy)) or 0,
            "poza": sum(1 for p in pomiary if p.w_tolerancji is False),
        },
    )


@wykonanie_bp.post("/wykonanie/dodaj")
def dodaj():
    dotyczy = request.form.get("dotyczy", "")
    obiekt, odcinek, blad = _powiaz(dotyczy)
    if blad:
        flash(blad, "danger")
        return redirect(request.referrer or url_for("wykonanie.dziennik"))

    try:
        rzedna = float((request.form.get("rzedna") or "").replace(",", "."))
    except ValueError:
        flash("Rzędna musi być liczbą, np. 82,76.", "danger")
        return redirect(request.referrer or url_for("wykonanie.dziennik"))

    odleglosc = (request.form.get("odleglosc") or "").replace(",", ".").strip()
    rodzaj = request.form.get("rodzaj", RodzajPomiaru.DNO_KANALU.value)

    pomiar = PomiarWykonawczy(
        obiekt_id=obiekt.id if obiekt else None,
        segment_id=odcinek.id if odcinek else None,
        rodzaj=RodzajPomiaru[rodzaj] if rodzaj in RodzajPomiaru.__members__
        else RodzajPomiaru.DNO_KANALU,
        rzedna_zmierzona=rzedna,
        odleglosc_m=float(odleglosc) if odleglosc else None,
        uwagi=(request.form.get("uwagi") or "").strip() or None,
        autor_id=current_user.id if current_user.is_authenticated else None,
    )
    data_pomiaru = (request.form.get("data") or "").strip()
    if data_pomiaru:
        pomiar.data_pomiaru = date.fromisoformat(data_pomiaru)

    db.session.add(pomiar)
    db.session.commit()

    odchylka = pomiar.odchylka_m
    if odchylka is None:
        flash(f"Zapisano pomiar {pomiar.czego_dotyczy}. "
              "Projekt nie podaje rzędnej, więc nie ma do czego porównać.", "info")
    elif pomiar.w_tolerancji:
        flash(f"Zapisano. {pomiar.czego_dotyczy}: odchyłka {odchylka:+.3f} m — "
              f"w tolerancji ({pomiar.tolerancja_m:.2f} m).", "success")
    else:
        flash(f"Zapisano, ale UWAGA: {pomiar.czego_dotyczy} odbiega od projektu "
              f"o {odchylka:+.3f} m przy tolerancji {pomiar.tolerancja_m:.2f} m.", "warning")

    return redirect(request.referrer or url_for("wykonanie.dziennik"))


@wykonanie_bp.post("/wykonanie/<int:pomiar_id>/usun")
def usun(pomiar_id: int):
    pomiar = db.session.get(PomiarWykonawczy, pomiar_id)
    if pomiar is None:
        flash("Nie ma takiego pomiaru.", "warning")
        return redirect(url_for("wykonanie.dziennik"))

    wlasny = pomiar.autor_id == getattr(current_user, "id", None)
    if not (wlasny or getattr(current_user, "jest_adminem", False)):
        flash("Usunąć pomiar może jego autor albo administrator.", "danger")
        return redirect(url_for("wykonanie.dziennik"))

    db.session.delete(pomiar)
    db.session.commit()
    flash("Pomiar usunięty.", "success")
    return redirect(request.referrer or url_for("wykonanie.dziennik"))


@wykonanie_bp.get("/api/wykonanie/odcinek/<od>/<do_>")
def api_odcinek(od: str, do_: str):
    """Wykonanie jednego odcinka - pomiary, odchylki i rzeczywisty spadek."""
    _, odcinek, blad = _powiaz(f"{od}-{do_}")
    if odcinek is None:
        return jsonify({"blad": blad or f"Nie ma odcinka {od}-{do_}."}), 404

    podsumowanie = podsumowanie_odcinka(odcinek)
    if podsumowanie is None:
        return jsonify({"odcinek": odcinek.nazwa, "pomiarow": 0, "pomiary": []})

    pomiary = podsumowanie.pop("pomiary")
    return jsonify({
        "odcinek": odcinek.nazwa,
        **podsumowanie,
        "pomiary": [p.to_dict() for p in pomiary],
    })
