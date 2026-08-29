"""Wyszukiwarka: jedno pole, komplet informacji o odcinku.

Po wpisaniu `D155` brygadzista dostaje nie sam wiersz tabeli, tylko wszystko,
co jest potrzebne do wejscia w wykop: rzedne obiektu, kazdy odcinek z jego
udzialem wraz z rysunkiem profilu, wykaz materialow i przelicznik rur
w trzech wariantach.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    Connection,
    NetworkObject,
    PlanLocation,
    Segment,
    SurveyPoint,
)
from app.models.plan import punkty_na_metry
from app.services.materialy import wykaz_dla_odcinka

szukaj_bp = Blueprint("szukaj", __name__)

LIMIT_PODPOWIEDZI = 12


def znajdz_obiekt(fraza: str) -> NetworkObject | None:
    """Najpierw dokladne trafienie, potem najkrotszy pasujacy kod."""
    fraza = fraza.strip()
    if not fraza:
        return None
    ob = db.session.scalar(
        select(NetworkObject).where(func.lower(NetworkObject.kod) == fraza.lower())
    )
    if ob is not None:
        return ob
    return db.session.scalar(
        select(NetworkObject)
        .where(NetworkObject.kod.ilike(f"{fraza}%"))
        .order_by(func.length(NetworkObject.kod), NetworkObject.kod)
    )


def odcinki_obiektu(ob: NetworkObject) -> list[Segment]:
    q = (
        select(Segment)
        .where(or_(Segment.obiekt_od_id == ob.id, Segment.obiekt_do_id == ob.id))
        .options(
            selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do),
            selectinload(Segment.profil),
        )
        .order_by(Segment.kolejnosc)
    )
    return list(db.session.scalars(q))


def lokalizacja(ob: NetworkObject) -> PlanLocation | None:
    return db.session.scalar(
        select(PlanLocation)
        .where(PlanLocation.obiekt_id == ob.id)
        .options(selectinload(PlanLocation.strona))
        .order_by(PlanLocation.zweryfikowane.desc(), PlanLocation.pewnosc.desc())
    )


def repery_najblizsze(ob: NetworkObject, ile: int = 5) -> dict:
    """Repery najblizsze GEOMETRYCZNIE.

    Wymaga, zeby i obiekt, i repery mialy zapisana pozycje na planie. Dopoki jej
    nie ma, nie zgadujemy - mowimy wprost, czego brakuje.
    """
    lok = lokalizacja(ob)
    if lok is None or lok.strona is None:
        return {"dostepne": False, "repery": [],
                "powod": "Obiekt nie ma jeszcze wskazanej pozycji na planie sytuacyjnym."}

    zlokalizowane = db.session.scalar(
        select(func.count()).select_from(PlanLocation)
        .join(NetworkObject, PlanLocation.obiekt_id == NetworkObject.id)
        .where(PlanLocation.strona_id == lok.strona_id)
    )
    if not zlokalizowane:
        return {"dostepne": False, "repery": [],
                "powod": "Na tej stronie planu nie ma jeszcze zlokalizowanych reperow."}

    # Odleglosci liczone w punktach PDF i przeliczane skala rysunku na metry.
    sasiedzi = db.session.scalars(
        select(PlanLocation)
        .where(PlanLocation.strona_id == lok.strona_id, PlanLocation.obiekt_id != ob.id)
        .options(selectinload(PlanLocation.obiekt))
    )
    skala = lok.strona.skala or 1000
    lista = []
    for s in sasiedzi:
        dx = float(s.x_pt) - float(lok.x_pt)
        dy = float(s.y_pt) - float(lok.y_pt)
        lista.append({
            "kod": s.obiekt.kod if s.obiekt else None,
            "odleglosc_m": punkty_na_metry((dx * dx + dy * dy) ** 0.5, skala),
            "pewna": s.pewna,
        })
    lista.sort(key=lambda w: w["odleglosc_m"])
    return {"dostepne": True, "repery": lista[:ile], "powod": None}


def repery_wysokosciowo(ob: NetworkObject, ile: int = 5) -> list[dict]:
    """Repery o rzednej zblizonej do terenu przy obiekcie.

    To NIE sa repery najblizsze w terenie - to podpowiedz, z ktorego repera
    wygodnie sie nawiazac: przy zblizonej wysokosci odczyt zmiesci sie na lacie
    (4 m) bez przestawiania stanowiska.
    """
    if ob.rzedna_terenu_proj is None:
        return []
    teren = float(ob.rzedna_terenu_proj)
    q = (
        select(SurveyPoint)
        .where(SurveyPoint.h.isnot(None), SurveyPoint.aktywny.is_(True))
        .order_by(func.abs(SurveyPoint.h - teren))
        .limit(ile)
    )
    return [
        {**p.to_dict(), "roznica_wysokosci": round(float(p.h) - teren, 3)}
        for p in db.session.scalars(q)
    ]


def zbuduj_wynik(ob: NetworkObject) -> dict:
    odcinki = odcinki_obiektu(ob)
    lok = lokalizacja(ob)
    return {
        "obiekt": ob,
        "odcinki": [
            {"segment": o, "wykaz": wykaz_dla_odcinka(o)} for o in odcinki
        ],
        "polaczenia": list(db.session.scalars(
            select(Connection).where(Connection.obiekt_id == ob.id)
        )),
        "lokalizacja": lok,
        "repery_wysokosciowo": repery_wysokosciowo(ob),
        "repery_najblizsze": repery_najblizsze(ob),
    }


@szukaj_bp.get("/szukaj")
def szukaj():
    fraza = (request.args.get("q") or "").strip()
    if not fraza:
        return render_template("pages/szukaj.html", fraza="", wynik=None, podobne=[])

    ob = znajdz_obiekt(fraza)
    podobne = list(db.session.scalars(
        select(NetworkObject)
        .where(NetworkObject.kod.ilike(f"%{fraza}%"))
        .order_by(func.length(NetworkObject.kod), NetworkObject.kod)
        .limit(LIMIT_PODPOWIEDZI)
    ))
    wynik = zbuduj_wynik(ob) if ob else None
    return render_template("pages/szukaj.html", fraza=fraza, wynik=wynik, podobne=podobne)


@szukaj_bp.get("/api/szukaj")
def api_szukaj():
    fraza = (request.args.get("q") or "").strip()
    ob = znajdz_obiekt(fraza)
    if ob is None:
        return jsonify({"blad": f"Nie znalazłem obiektu pasującego do „{fraza}”."}), 404

    odcinki = odcinki_obiektu(ob)
    lok = lokalizacja(ob)
    return jsonify({
        "obiekt": ob.to_dict(),
        "odcinki": [
            {**o.to_dict(), "wykaz_materialow": wykaz_dla_odcinka(o)} for o in odcinki
        ],
        "polaczenia": [
            c.to_dict() for c in db.session.scalars(
                select(Connection).where(Connection.obiekt_id == ob.id)
            )
        ],
        "lokalizacja_na_planie": lok.to_dict() if lok else None,
        "repery_wysokosciowo": repery_wysokosciowo(ob),
        "repery_najblizsze": repery_najblizsze(ob),
    })


@szukaj_bp.get("/api/podpowiedzi")
def podpowiedzi():
    """Podpowiedzi do pola wyszukiwania (jQuery)."""
    fraza = (request.args.get("q") or "").strip()
    if len(fraza) < 1:
        return jsonify([])
    q = (
        select(NetworkObject.kod, NetworkObject.typ)
        .where(NetworkObject.kod.ilike(f"{fraza}%"))
        .order_by(func.length(NetworkObject.kod), NetworkObject.kod)
        .limit(LIMIT_PODPOWIEDZI)
    )
    return jsonify([{"kod": k, "typ": t.value} for k, t in db.session.execute(q)])


@szukaj_bp.get("/odcinek/<od>/<do_>/karta")
def karta_do_druku(od: str, do_: str):
    """Karta odcinka na jedna kartke A4 - do teczki wykonawczej.

    Wszystko, co brygada ma przy sobie w wykopie: profil, rzedne, spadek,
    ile rur i jakich, wykaz materialow, wycinek oryginalnego rysunku
    i miejsce na wpisanie pomiarow recznie.
    """
    from sqlalchemy.orm import aliased

    a, b = aliased(NetworkObject), aliased(NetworkObject)
    odcinek = db.session.scalar(
        select(Segment).join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
        .where(func.lower(a.kod) == od.lower(), func.lower(b.kod) == do_.lower())
    )
    if odcinek is None:
        from flask import abort

        abort(404, f"Nie ma odcinka {od}-{do_}.")

    from app.blueprints.wykonanie import podsumowanie_odcinka

    return render_template(
        "pages/karta_druk.html",
        o=odcinek,
        wykaz=wykaz_dla_odcinka(odcinek),
        wykonanie=podsumowanie_odcinka(odcinek),
    )


@szukaj_bp.get("/api/odcinek/<od>/<do_>/rury")
def rury_odcinka(od: str, do_: str):
    """Sam przelicznik rur dla wskazanego odcinka."""
    from sqlalchemy.orm import aliased

    a, b = aliased(NetworkObject), aliased(NetworkObject)
    o = db.session.scalar(
        select(Segment).join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id).where(a.kod == od, b.kod == do_)
    )
    if o is None:
        return jsonify({"blad": f"Nie ma odcinka {od}-{do_}"}), 404
    return jsonify(wykaz_dla_odcinka(o))
