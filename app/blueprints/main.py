"""Widoki HTML."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request, send_file
from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

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

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def pulpit():
    from app.blueprints.mapa import zapewnij_strony

    try:
        strony_planu = zapewnij_strony()
    except Exception:  # noqa: BLE001 - brak pliku planow nie moze wywalac pulpitu
        db.session.rollback()
        strony_planu = []
    wybrana = request.args.get("plan", type=int)
    strona_planu = next((s for s in strony_planu if s.nr_strony == wybrana),
                        strony_planu[0] if strony_planu else None)
    typy = db.session.execute(
        select(NetworkObject.typ, func.count())
        .group_by(NetworkObject.typ).order_by(func.count().desc())
    ).all()
    srednice = db.session.execute(
        select(Segment.dn_mm, func.count(), func.sum(Segment.dlugosc_m))
        .where(Segment.dn_mm.isnot(None))
        .group_by(Segment.dn_mm).order_by(Segment.dn_mm)
    ).all()
    return render_template(
        "pages/pulpit.html",
        liczby={
            "profile": db.session.scalar(select(func.count()).select_from(Profile)),
            "obiekty": db.session.scalar(select(func.count()).select_from(NetworkObject)),
            "odcinki": db.session.scalar(select(func.count()).select_from(Segment)),
            "osnowa": db.session.scalar(select(func.count()).select_from(SurveyPoint)),
            "materialy": db.session.scalar(select(func.count()).select_from(MaterialItem)),
            "dlugosc": float(db.session.scalar(select(func.sum(Segment.dlugosc_m))) or 0),
        },
        typy=typy,
        srednice=srednice,
        importy=list(db.session.scalars(
            select(ImportRun).order_by(ImportRun.rozpoczeto.desc()).limit(6)
        )),
        strony_planu=strony_planu,
        strona_planu=strona_planu,
    )


@main_bp.get("/odcinki")
def odcinki():
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    szukaj = request.args.get("szukaj", "").strip()
    q = (
        select(Segment)
        .join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
        .options(selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do),
                 selectinload(Segment.profil))
    )
    if szukaj:
        q = q.where(a.kod.ilike(f"%{szukaj}%") | b.kod.ilike(f"%{szukaj}%"))
    q = q.order_by(a.kod, Segment.kolejnosc).limit(500)
    return render_template("pages/odcinki.html", odcinki=list(db.session.scalars(q)), szukaj=szukaj)


@main_bp.get("/obiekty")
def obiekty():
    szukaj = request.args.get("szukaj", "").strip()
    typ = request.args.get("typ", "").strip()
    q = select(NetworkObject)
    if szukaj:
        q = q.where(NetworkObject.kod.ilike(f"%{szukaj}%"))
    if typ and typ in TypObiektu.__members__:
        q = q.where(NetworkObject.typ == TypObiektu[typ])
    q = q.order_by(NetworkObject.kod).limit(500)
    return render_template(
        "pages/obiekty.html", obiekty=list(db.session.scalars(q)),
        szukaj=szukaj, typ=typ, typy=list(TypObiektu),
    )


@main_bp.get("/obiekt/<kod>")
def obiekt(kod: str):
    ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if ob is None:
        abort(404, f"Nie ma obiektu {kod}")
    polaczenia = list(db.session.scalars(
        select(Connection).where(Connection.obiekt_id == ob.id)
    ))
    return render_template("pages/obiekt.html", ob=ob, polaczenia=polaczenia)


@main_bp.get("/profil/<int:profil_id>")
def profil(profil_id: int):
    p = db.session.get(Profile, profil_id)
    if p is None:
        abort(404)
    return render_template("pages/profil.html", p=p)


# --------------------------------------------------- wycinek z oryginalu

def _wycinek_profilu(p: Profile, z_legenda: bool):
    """Fragment oryginalnego rysunku dla profilu - liczony dopiero na zadanie.

    Konwersja PDF kosztuje, wiec nie odpala sie przy wysietleniu strony.
    Dopiero klikniecie "Pokaz wycinek" siega po ten kod, a wynik zostaje
    w cache na dysku.
    """
    from app.services.wycinek_pdf import do_cache, klucz_cache, wytnij, z_cache

    if p.sheet is None or not p.bbox:
        abort(404, "Ten profil nie ma zapisanego polozenia na arkuszu.")

    sciezka = Path(current_app.config["DOCS_DIR"]) / p.sheet.plik
    if not sciezka.exists():
        abort(404, f"Brak pliku {p.sheet.plik} w katalogu docs/.")

    x_od = float(p.bbox.get("x_od", 0.0))
    x_do = float(p.bbox.get("x_do", 0.0))
    katalog = Path(current_app.config["EXPORT_DIR"]) / "wycinki"
    nazwa_pdf = klucz_cache(p.sheet.nr_strony, x_od, x_do, z_legenda, ".pdf")

    dane = z_cache(katalog, nazwa_pdf)
    if dane is None:
        dane = wytnij(sciezka, p.sheet.nr_strony, x_od, x_do, z_legenda).pdf
        do_cache(katalog, nazwa_pdf, dane)
    return dane, katalog, (p.sheet.nr_strony, x_od, x_do)


@main_bp.get("/profil/<int:profil_id>/wycinek.pdf")
def wycinek_profilu_pdf(profil_id: int):
    """Wektorowy fragment oryginalu - do obejrzenia w powiekszeniu i do druku."""
    p = db.session.get(Profile, profil_id)
    if p is None:
        abort(404)
    z_legenda = request.args.get("legenda", "1") != "0"
    dane, _, _ = _wycinek_profilu(p, z_legenda)
    return send_file(
        BytesIO(dane), mimetype="application/pdf",
        download_name=f"profil-{p.oznaczenie}-oryginal.pdf",
        as_attachment=request.args.get("pobierz") == "1",
    )


@main_bp.get("/profil/<int:profil_id>/wycinek.png")
def wycinek_profilu_png(profil_id: int):
    from app.services.wycinek_pdf import DPI_PODGLAD, Wycinek, do_cache, klucz_cache, z_cache

    p = db.session.get(Profile, profil_id)
    if p is None:
        abort(404)
    z_legenda = request.args.get("legenda", "1") != "0"
    dpi = min(max(request.args.get("dpi", DPI_PODGLAD, type=int), 60), 400)

    dane, katalog, (nr, x_od, x_do) = _wycinek_profilu(p, z_legenda)
    nazwa_png = klucz_cache(nr, x_od, x_do, z_legenda, ".png", dpi)
    obraz = z_cache(katalog, nazwa_png)
    if obraz is None:
        obraz = Wycinek(dane, nr, x_od, x_do, 0, 0, z_legenda).png(dpi)
        do_cache(katalog, nazwa_png, obraz)
    return send_file(BytesIO(obraz), mimetype="image/png")


def _zakres_odcinka(odc: Segment) -> tuple[float, float] | None:
    """Polozenie na arkuszu kolumn obu koncow odcinka.

    Profil bywa dlugi na kilkanascie wezlow; do sprawdzenia jednego odcinka
    wystarcza dwie kolumny, a im wezszy wycinek, tym wieksza skala rysunku.
    """
    wystapienia = list(db.session.scalars(
        select(ObjectOccurrence).where(
            ObjectOccurrence.profil_id == odc.profil_id,
            ObjectOccurrence.obiekt_id.in_([odc.obiekt_od_id, odc.obiekt_do_id]),
        )
    ))
    krance = [w.bbox for w in wystapienia if w.bbox and "x0" in w.bbox]
    if len(krance) < 2:
        return None
    return (min(float(b["x0"]) for b in krance),
            max(float(b["x1"]) for b in krance))


def _znajdz_odcinek(od: str, do_: str) -> Segment:
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    odc = db.session.scalar(
        select(Segment).join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id).where(a.kod == od, b.kod == do_)
    )
    if odc is None:
        abort(404, f"Nie ma odcinka {od}-{do_}.")
    return odc


@main_bp.get("/odcinek/<od>/<do_>/wycinek.png")
def wycinek_odcinka_png(od: str, do_: str):
    """Fragment oryginalu obejmujacy tylko ten jeden odcinek."""
    from app.services.wycinek_pdf import DPI_PODGLAD, Wycinek, do_cache, klucz_cache, wytnij, z_cache

    odc = _znajdz_odcinek(od, do_)
    profil = odc.profil
    if profil is None or profil.sheet is None:
        abort(404, "Ten odcinek nie ma przypisanego profilu na arkuszu.")

    zakres = _zakres_odcinka(odc)
    if zakres is None and profil.bbox:
        zakres = (float(profil.bbox.get("x_od", 0.0)), float(profil.bbox.get("x_do", 0.0)))
    if zakres is None:
        abort(404, "Nie znam położenia tego odcinka na arkuszu.")

    sciezka = Path(current_app.config["DOCS_DIR"]) / profil.sheet.plik
    if not sciezka.exists():
        abort(404, f"Brak pliku {profil.sheet.plik} w katalogu docs/.")

    dpi = min(max(request.args.get("dpi", DPI_PODGLAD, type=int), 60), 400)
    katalog = Path(current_app.config["EXPORT_DIR"]) / "wycinki"
    nr = profil.sheet.nr_strony
    nazwa_png = klucz_cache(nr, zakres[0], zakres[1], True, ".png", dpi)

    obraz = z_cache(katalog, nazwa_png)
    if obraz is None:
        wycinek = wytnij(sciezka, nr, zakres[0], zakres[1])
        do_cache(katalog, klucz_cache(nr, zakres[0], zakres[1], True, ".pdf"), wycinek.pdf)
        obraz = wycinek.png(dpi)
        do_cache(katalog, nazwa_png, obraz)
    return send_file(BytesIO(obraz), mimetype="image/png")


@main_bp.get("/odcinek/<od>/<do_>/wycinek.pdf")
def wycinek_odcinka_pdf(od: str, do_: str):
    from app.services.wycinek_pdf import do_cache, klucz_cache, wytnij, z_cache

    odc = _znajdz_odcinek(od, do_)
    profil = odc.profil
    if profil is None or profil.sheet is None:
        abort(404, "Ten odcinek nie ma przypisanego profilu na arkuszu.")

    zakres = _zakres_odcinka(odc)
    if zakres is None and profil.bbox:
        zakres = (float(profil.bbox.get("x_od", 0.0)), float(profil.bbox.get("x_do", 0.0)))
    if zakres is None:
        abort(404, "Nie znam położenia tego odcinka na arkuszu.")

    sciezka = Path(current_app.config["DOCS_DIR"]) / profil.sheet.plik
    if not sciezka.exists():
        abort(404, f"Brak pliku {profil.sheet.plik} w katalogu docs/.")

    katalog = Path(current_app.config["EXPORT_DIR"]) / "wycinki"
    nr = profil.sheet.nr_strony
    nazwa = klucz_cache(nr, zakres[0], zakres[1], True, ".pdf")
    dane = z_cache(katalog, nazwa)
    if dane is None:
        dane = wytnij(sciezka, nr, zakres[0], zakres[1]).pdf
        do_cache(katalog, nazwa, dane)
    return send_file(
        BytesIO(dane), mimetype="application/pdf",
        download_name=f"odcinek-{od}-{do_}-oryginal.pdf",
        as_attachment=request.args.get("pobierz") == "1",
    )


@main_bp.get("/profile")
def profile():
    szukaj = request.args.get("szukaj", "").strip()
    q = select(Profile).options(selectinload(Profile.sheet))
    if szukaj:
        q = q.where(Profile.oznaczenie.ilike(f"%{szukaj}%"))
    q = q.order_by(Profile.oznaczenie).limit(500)
    return render_template("pages/profile.html", profile=list(db.session.scalars(q)), szukaj=szukaj)


@main_bp.get("/osnowa")
def osnowa():
    q = select(SurveyPoint).order_by(SurveyPoint.nazwa)
    return render_template("pages/osnowa.html", punkty=list(db.session.scalars(q)))


@main_bp.get("/materialy")
def materialy():
    q = select(MaterialItem).order_by(MaterialItem.opis_pozycji).limit(500)
    return render_template("pages/materialy.html", pozycje=list(db.session.scalars(q)))


@main_bp.get("/importy")
def importy():
    q = select(ImportRun).order_by(ImportRun.rozpoczeto.desc()).limit(50)
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    podejrzane = list(db.session.scalars(
        select(Segment)
        .join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id)
        .where(Segment.podejrzany.is_(True))
        .options(selectinload(Segment.obiekt_od), selectinload(Segment.obiekt_do),
                 selectinload(Segment.profil))
        .order_by(a.kod)
    ))
    return render_template("pages/importy.html", importy=list(db.session.scalars(q)),
                           podejrzane=podejrzane)
