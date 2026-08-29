"""Plany sytuacyjne: przegladanie arkuszy i wskazywanie pozycji obiektow.

Etykiety na planach sa zamienione na krzywe, wiec automat ich nie odczyta
(patrz `app/services/plan_ocr.py`). Zamiast udawac, ze wiemy, gdzie lezy obiekt,
dajemy dwie drogi:

  * **przegladarka arkuszy** - kazda strone da sie obejrzec i przyblizyc,
  * **wskazanie pozycji** - klikniecie na mapie zapisuje wspolrzedne obiektu.

Od momentu wskazania dzialaja juz odleglosci do sasiadow i wycinek mapy
wokol odcinka.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import fitz
from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file
from sqlalchemy import select
from sqlalchemy.orm import aliased, selectinload

from app.extensions import db
from app.models import NetworkObject, PlanLocation, PlanSheet, Segment

mapa_bp = Blueprint("mapa", __name__)

DPI_PODGLAD = 90
DPI_WYCINEK = 200
MARGINES_PT = 120.0     # ile dorysowac wokol odcinka


def _sciezka_planu() -> Path:
    return Path(current_app.config["DOCS_DIR"]) / "Plany sytuacyjne Scalone.pdf"


def _katalog_cache() -> Path:
    katalog = Path(current_app.config["EXPORT_DIR"]) / "mapy"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def zapewnij_strony() -> list[PlanSheet]:
    """Zarejestruj strony planu w bazie, jesli jeszcze ich nie ma."""
    plik = _sciezka_planu()
    if not plik.exists():
        return []
    istniejace = list(db.session.scalars(
        select(PlanSheet).where(PlanSheet.plik == plik.name).order_by(PlanSheet.nr_strony)
    ))
    if istniejace:
        return istniejace

    doc = fitz.open(plik)
    from app.services.plan_ocr import odczytaj_skale
    for nr in range(doc.page_count):
        page = doc[nr]
        db.session.add(PlanSheet(
            plik=plik.name, nr_strony=nr + 1,
            szerokosc_pt=round(page.rect.width, 2),
            wysokosc_pt=round(page.rect.height, 2),
            skala=odczytaj_skale(page),
        ))
    doc.close()
    db.session.commit()
    return list(db.session.scalars(
        select(PlanSheet).where(PlanSheet.plik == plik.name).order_by(PlanSheet.nr_strony)
    ))


def _renderuj(nr_strony: int, clip: fitz.Rect | None, dpi: int,
              zaznacz: list[tuple[float, float]] | None = None) -> bytes:
    plik = _sciezka_planu()
    if not plik.exists():
        abort(404, "Brak pliku planów sytuacyjnych w katalogu docs/.")

    klucz = f"{nr_strony}|{clip}|{dpi}|{zaznacz}"
    nazwa = hashlib.sha1(klucz.encode()).hexdigest()[:20] + ".png"
    plik_cache = _katalog_cache() / nazwa
    if plik_cache.exists():
        return plik_cache.read_bytes()

    doc = fitz.open(plik)
    if not 1 <= nr_strony <= doc.page_count:
        doc.close()
        abort(404, f"Plan ma {doc.page_count} stron, nie ma strony {nr_strony}.")
    page = doc[nr_strony - 1]

    if zaznacz:
        # Kolko wokol wskazanej pozycji - rysowane na kopii, plik zrodlowy nietkniety.
        shape = page.new_shape()
        for x, y in zaznacz:
            shape.draw_circle(fitz.Point(x, y), 18)
            shape.finish(color=(1, 0, 0), width=3.0)
            shape.draw_line(fitz.Point(x - 28, y), fitz.Point(x - 22, y))
            shape.draw_line(fitz.Point(x + 22, y), fitz.Point(x + 28, y))
            shape.finish(color=(1, 0, 0), width=3.0)
        shape.commit()

    pix = page.get_pixmap(dpi=dpi, clip=clip)
    dane = pix.tobytes("png")
    doc.close()
    plik_cache.write_bytes(dane)
    return dane


@mapa_bp.get("/mapa")
def przegladarka():
    strony = zapewnij_strony()
    nr = int(request.args.get("strona", 1))
    strona = next((s for s in strony if s.nr_strony == nr), strony[0] if strony else None)
    lokalizacje = []
    if strona:
        lokalizacje = list(db.session.scalars(
            select(PlanLocation).where(PlanLocation.strona_id == strona.id)
            .options(selectinload(PlanLocation.obiekt))
        ))
    return render_template("pages/mapa.html", strony=strony, strona=strona,
                           lokalizacje=lokalizacje)


@mapa_bp.get("/mapa/strona/<int:nr>.png")
def strona_png(nr: int):
    dpi = min(int(request.args.get("dpi", DPI_PODGLAD)), 200)
    return send_file(BytesIO(_renderuj(nr, None, dpi)), mimetype="image/png")


@mapa_bp.get("/mapa/obiekt/<kod>.png")
def obiekt_png(kod: str):
    """Wycinek planu wokol jednego obiektu, z zaznaczeniem."""
    ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if ob is None:
        abort(404, f"Nie ma obiektu {kod}.")
    lok = db.session.scalar(
        select(PlanLocation).where(PlanLocation.obiekt_id == ob.id)
        .options(selectinload(PlanLocation.strona))
        .order_by(PlanLocation.zweryfikowane.desc(), PlanLocation.pewnosc.desc())
    )
    if lok is None:
        abort(404, f"Obiekt {kod} nie ma jeszcze wskazanej pozycji na planie.")

    x, y = float(lok.x_pt), float(lok.y_pt)
    clip = fitz.Rect(x - MARGINES_PT, y - MARGINES_PT, x + MARGINES_PT, y + MARGINES_PT)
    dane = _renderuj(lok.strona.nr_strony, clip, DPI_WYCINEK, zaznacz=[(x, y)])
    return send_file(BytesIO(dane), mimetype="image/png")


@mapa_bp.get("/mapa/odcinek/<od>/<do_>.png")
def odcinek_png(od: str, do_: str):
    """Wycinek obejmujacy oba konce odcinka."""
    a, b = aliased(NetworkObject), aliased(NetworkObject)
    odc = db.session.scalar(
        select(Segment).join(a, Segment.obiekt_od_id == a.id)
        .join(b, Segment.obiekt_do_id == b.id).where(a.kod == od, b.kod == do_)
    )
    if odc is None:
        abort(404, f"Nie ma odcinka {od}-{do_}.")

    punkty, strona = [], None
    for ob in (odc.obiekt_od, odc.obiekt_do):
        lok = db.session.scalar(
            select(PlanLocation).where(PlanLocation.obiekt_id == ob.id)
            .options(selectinload(PlanLocation.strona))
            .order_by(PlanLocation.zweryfikowane.desc(), PlanLocation.pewnosc.desc())
        )
        if lok is not None:
            punkty.append((float(lok.x_pt), float(lok.y_pt)))
            strona = lok.strona
    if not punkty or strona is None:
        abort(404, f"Ani {od}, ani {do_} nie ma jeszcze pozycji na planie.")

    xs = [p[0] for p in punkty]
    ys = [p[1] for p in punkty]
    clip = fitz.Rect(min(xs) - MARGINES_PT, min(ys) - MARGINES_PT,
                     max(xs) + MARGINES_PT, max(ys) + MARGINES_PT)
    dane = _renderuj(strona.nr_strony, clip, DPI_WYCINEK, zaznacz=punkty)
    return send_file(BytesIO(dane), mimetype="image/png")


@mapa_bp.post("/api/mapa/pozycja")
def zapisz_pozycje():
    """Recznie wskazana pozycja obiektu na planie - zawsze traktowana jako pewna."""
    dane = request.get_json(silent=True) or {}
    kod = (dane.get("kod") or "").strip()
    ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if ob is None:
        return jsonify({"blad": f"Nie ma obiektu {kod}."}), 404

    strona = db.session.get(PlanSheet, int(dane.get("strona_id", 0)))
    if strona is None:
        return jsonify({"blad": "Nie ma takiej strony planu."}), 404
    try:
        x, y = float(dane["x_pt"]), float(dane["y_pt"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"blad": "Wymagane: x_pt, y_pt."}), 400

    lok = db.session.scalar(
        select(PlanLocation).where(PlanLocation.obiekt_id == ob.id,
                                   PlanLocation.strona_id == strona.id)
    )
    if lok is None:
        lok = PlanLocation(obiekt_id=ob.id, strona_id=strona.id)
        db.session.add(lok)
    lok.x_pt, lok.y_pt = x, y
    lok.zrodlo = "RECZNIE"
    lok.zweryfikowane = True
    lok.pewnosc = 100
    db.session.commit()
    return jsonify({"zapisano": True, "lokalizacja": lok.to_dict()})


@mapa_bp.delete("/api/mapa/pozycja/<kod>")
def usun_pozycje(kod: str):
    ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if ob is None:
        return jsonify({"blad": f"Nie ma obiektu {kod}."}), 404
    usuniete = 0
    for lok in db.session.scalars(select(PlanLocation).where(PlanLocation.obiekt_id == ob.id)):
        db.session.delete(lok)
        usuniete += 1
    db.session.commit()
    return jsonify({"usunieto": usuniete})
