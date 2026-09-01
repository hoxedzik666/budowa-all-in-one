"""API JSON - warstwa danych dla front-endu (jQuery) i integracji."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased, selectinload

from app.config import czy_termux
from app.extensions import db
from app.models import (
    Connection,
    ImportRun,
    MaterialItem,
    NetworkObject,
    ObjectOccurrence,
    Profile,
    Segment,
    SurveyPoint,
    TypObiektu,
)
from app.services.opcjonalne import dostepne

api_bp = Blueprint("api", __name__)


@api_bp.get("/zdrowie")
def zdrowie():
    """Czy serwer zyje - i na czym stoi.

    Pole `status` sprawdza ekran konfiguracji w APK, zanim zapisze adres serwera,
    wiec jego nazwa i wartosc sa czescia umowy z aplikacja (`.apk/web/shell.js`).
    Reszta pol to diagnostyka: na telefonie od razu widac, czy baza to plik
    SQLite i ktorych bibliotek opcjonalnych brakuje - bez wchodzenia do logow.
    """
    db.session.execute(select(1))
    return jsonify({
        "status": "ok",
        "baza": db.engine.dialect.name,
        "termux": czy_termux(),
        "moduly": dostepne(),
    })


@api_bp.get("/statystyki")
def statystyki():
    typy = db.session.execute(
        select(NetworkObject.typ, func.count()).group_by(NetworkObject.typ)
    ).all()
    return jsonify({
        "profile": db.session.scalar(select(func.count()).select_from(Profile)),
        "obiekty": db.session.scalar(select(func.count()).select_from(NetworkObject)),
        "odcinki": db.session.scalar(select(func.count()).select_from(Segment)),
        "punkty_osnowy": db.session.scalar(select(func.count()).select_from(SurveyPoint)),
        "materialy": db.session.scalar(select(func.count()).select_from(MaterialItem)),
        "dlugosc_calkowita_m": float(db.session.scalar(select(func.sum(Segment.dlugosc_m))) or 0),
        "wg_typu": {t.value: n for t, n in typy},
    })


@api_bp.get("/obiekty")
def obiekty():
    q = select(NetworkObject)
    if (szukaj := request.args.get("szukaj")):
        q = q.where(NetworkObject.kod.ilike(f"%{szukaj}%"))
    if (typ := request.args.get("typ")):
        q = q.where(NetworkObject.typ == TypObiektu[typ])
    limit = min(int(request.args.get("limit", 200)), 2000)
    q = q.order_by(NetworkObject.kod).limit(limit)
    return jsonify([o.to_dict() for o in db.session.scalars(q)])


@api_bp.get("/obiekty/<kod>")
def obiekt(kod: str):
    ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if ob is None:
        return jsonify({"blad": f"Nie ma obiektu {kod}"}), 404
    dane = ob.to_dict()
    dane["wystapienia"] = [
        {"profil": w.profil.oznaczenie, "nr_strony": w.profil.sheet.nr_strony if w.profil.sheet else None,
         "hektometr": float(w.hektometr) if w.hektometr is not None else None,
         "rzedna_dna": float(w.rzedna_dna) if w.rzedna_dna is not None else None,
         "opis": w.opis}
        for w in ob.wystapienia
    ]
    dane["odcinki_wychodzace"] = [o.to_dict() for o in ob.odcinki_wychodzace]
    dane["odcinki_wchodzace"] = [o.to_dict() for o in ob.odcinki_wchodzace]
    dane["polaczenia"] = [
        c.to_dict() for c in db.session.scalars(
            select(Connection).where(Connection.obiekt_id == ob.id)
        )
    ]
    return jsonify(dane)


@api_bp.get("/odcinki")
def odcinki():
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    q = (
        select(Segment)
        .join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
        .options(selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do))
    )
    if (szukaj := request.args.get("szukaj")):
        q = q.where(or_(a.kod.ilike(f"%{szukaj}%"), b.kod.ilike(f"%{szukaj}%")))
    if (dn := request.args.get("dn")):
        q = q.where(Segment.dn_mm == int(dn))
    limit = min(int(request.args.get("limit", 300)), 3000)
    q = q.order_by(a.kod).limit(limit)
    return jsonify([o.to_dict() for o in db.session.scalars(q)])


@api_bp.get("/odcinki/<od>/<do_>")
def odcinek(od: str, do_: str):
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    o = db.session.scalar(
        select(Segment).join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id).where(a.kod == od, b.kod == do_)
    )
    if o is None:
        return jsonify({"blad": f"Nie ma odcinka {od}-{do_}"}), 404
    dane = o.to_dict()
    dane["obiekt_od"] = o.obiekt_od.to_dict()
    dane["obiekt_do"] = o.obiekt_do.to_dict()
    dane["profil"] = o.profil.to_dict() if o.profil else None
    return jsonify(dane)


@api_bp.get("/profile")
def profile():
    q = select(Profile).order_by(Profile.oznaczenie)
    if (szukaj := request.args.get("szukaj")):
        q = q.where(Profile.oznaczenie.ilike(f"%{szukaj}%"))
    return jsonify([p.to_dict() for p in db.session.scalars(q.limit(1000))])


@api_bp.get("/profile/<int:profil_id>")
def profil(profil_id: int):
    p = db.session.get(Profile, profil_id)
    if p is None:
        return jsonify({"blad": "Nie ma takiego profilu"}), 404
    return jsonify(p.to_dict(deep=True))


@api_bp.get("/osnowa")
def osnowa():
    q = select(SurveyPoint).order_by(SurveyPoint.nazwa)
    if (szukaj := request.args.get("szukaj")):
        q = q.where(SurveyPoint.nazwa.ilike(f"%{szukaj}%"))
    return jsonify([p.to_dict() for p in db.session.scalars(q)])


@api_bp.get("/materialy")
def materialy():
    q = select(MaterialItem).order_by(MaterialItem.opis_pozycji)
    return jsonify([m.to_dict() for m in db.session.scalars(q.limit(1000))])


@api_bp.get("/importy")
def importy():
    q = select(ImportRun).order_by(ImportRun.rozpoczeto.desc()).limit(30)
    return jsonify([b.to_dict() for b in db.session.scalars(q)])


@api_bp.get("/importy/<int:bieg_id>/ostrzezenia")
def ostrzezenia(bieg_id: int):
    b = db.session.get(ImportRun, bieg_id)
    if b is None:
        return jsonify({"blad": "Nie ma takiego importu"}), 404
    return jsonify({"plik": b.plik, "ostrzezenia": b.ostrzezenia or []})
