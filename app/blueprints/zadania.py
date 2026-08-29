"""Zadania - globalne i przypisane do kont."""
from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Blueprint, abort, flash, jsonify, redirect, request, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    OTWARTE,
    NetworkObject,
    Priorytet,
    Segment,
    StatusZadania,
    Task,
    User,
)

zadania_bp = Blueprint("zadania", __name__)


def widoczne_dla(uzytkownik, zakres: str = "wszystkie"):
    """Zadania globalne widzi kazdy, przypisane - tylko wlasciciel i kierownictwo."""
    q = select(Task).options(
        selectinload(Task.autor), selectinload(Task.przypisany_do),
        selectinload(Task.obiekt), selectinload(Task.segment),
    )
    if zakres == "moje":
        return q.where(Task.przypisany_do_id == uzytkownik.id)
    if zakres == "globalne":
        return q.where(Task.przypisany_do_id.is_(None))
    if uzytkownik.moze_przydzielac:
        return q
    # Brygadzista widzi swoje i globalne, nie cudze.
    return q.where(or_(Task.przypisany_do_id == uzytkownik.id,
                       Task.przypisany_do_id.is_(None)))


def licz_otwarte(uzytkownik) -> int:
    """Licznik do paska nawigacji: moje otwarte + globalne otwarte."""
    from sqlalchemy import func

    return db.session.scalar(
        select(func.count()).select_from(Task).where(
            Task.status.in_(OTWARTE),
            or_(Task.przypisany_do_id == uzytkownik.id, Task.przypisany_do_id.is_(None)),
        )
    ) or 0


@zadania_bp.get("/zadania")
@login_required
def lista():
    zakres = request.args.get("zakres", "wszystkie")
    status = request.args.get("status", "otwarte")

    q = widoczne_dla(current_user, zakres)
    if status == "otwarte":
        q = q.where(Task.status.in_(OTWARTE))
    elif status in StatusZadania.__members__:
        q = q.where(Task.status == StatusZadania[status])

    q = q.order_by(Task.status, Task.termin.nulls_last(), Task.id.desc())
    return render_template(
        "pages/zadania.html",
        zadania=list(db.session.scalars(q)),
        konta=list(db.session.scalars(
            select(User).where(User.aktywny.is_(True)).order_by(User.login)
        )),
        priorytety=list(Priorytet),
        statusy=list(StatusZadania),
        zakres=zakres, status=status,
    )


@zadania_bp.post("/zadania/dodaj")
@login_required
def dodaj():
    tytul = (request.form.get("tytul") or "").strip()
    if not tytul:
        flash("Zadanie musi mieć tytuł.", "warning")
        return redirect(url_for("zadania.lista"))

    zadanie = Task(tytul=tytul[:200], autor_id=current_user.id)
    zadanie.opis = (request.form.get("opis") or "").strip() or None

    priorytet = request.form.get("priorytet")
    if priorytet in Priorytet.__members__:
        zadanie.priorytet = Priorytet[priorytet]

    termin = (request.form.get("termin") or "").strip()
    if termin:
        try:
            zadanie.termin = date.fromisoformat(termin)
        except ValueError:
            flash("Nie rozpoznałem daty terminu — zadanie zapisane bez niego.", "warning")

    # Puste pole = zadanie globalne. Brygadzista moze przypisac tylko sobie.
    przypisany = (request.form.get("przypisany_do_id") or "").strip()
    if przypisany:
        if not current_user.moze_przydzielac and int(przypisany) != current_user.id:
            flash("Możesz przypisywać zadania tylko sobie.", "warning")
            return redirect(url_for("zadania.lista"))
        zadanie.przypisany_do_id = int(przypisany)

    kod = (request.form.get("dotyczy") or "").strip()
    if kod:
        _powiaz_z_siecia(zadanie, kod)

    db.session.add(zadanie)
    db.session.commit()
    flash("Dodano zadanie.", "success")
    return redirect(url_for("zadania.lista"))


def _powiaz_z_siecia(zadanie: Task, kod: str) -> None:
    """Kod obiektu (`D155`) albo odcinka (`Wyl101-D155`)."""
    if "-" in kod:
        od, _, do = kod.partition("-")
        from sqlalchemy.orm import aliased

        a, b = aliased(NetworkObject), aliased(NetworkObject)
        segment = db.session.scalar(
            select(Segment).join(a, Segment.obiekt_od_id == a.id)
            .join(b, Segment.obiekt_do_id == b.id)
            .where(a.kod == od.strip(), b.kod == do.strip())
        )
        if segment is not None:
            zadanie.segment_id = segment.id
            return
    obiekt = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if obiekt is not None:
        zadanie.obiekt_id = obiekt.id
    else:
        flash(f"Nie znam obiektu ani odcinka „{kod}” — zadanie zapisane bez powiązania.",
              "warning")


@zadania_bp.post("/zadania/<int:zid>/status")
@login_required
def zmien_status(zid: int):
    zadanie = db.session.get(Task, zid)
    if zadanie is None:
        abort(404)
    if not (current_user.moze_przydzielac
            or zadanie.przypisany_do_id in (None, current_user.id)):
        abort(403, "To nie jest Twoje zadanie.")

    nowy = request.form.get("status")
    if nowy not in StatusZadania.__members__:
        abort(400, "Nieznany status.")
    zadanie.status = StatusZadania[nowy]
    zadanie.zakonczono = (
        datetime.now(timezone.utc) if zadanie.status == StatusZadania.ZROBIONE else None
    )
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(zadanie.to_dict())
    return redirect(request.referrer or url_for("zadania.lista"))


@zadania_bp.post("/zadania/<int:zid>/usun")
@login_required
def usun(zid: int):
    zadanie = db.session.get(Task, zid)
    if zadanie is None:
        abort(404)
    if not (current_user.jest_adminem or zadanie.autor_id == current_user.id):
        abort(403, "Usunąć zadanie może jego autor albo administrator.")
    db.session.delete(zadanie)
    db.session.commit()
    flash("Usunięto zadanie.", "success")
    return redirect(url_for("zadania.lista"))


@zadania_bp.get("/api/zadania")
@login_required
def api_lista():
    zakres = request.args.get("zakres", "wszystkie")
    q = widoczne_dla(current_user, zakres).order_by(Task.id.desc()).limit(500)
    return jsonify([z.to_dict() for z in db.session.scalars(q)])
