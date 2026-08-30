"""Wysylka i podawanie zdjec z budowy."""
from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import PomiarWykonawczy, RaportDzienny, Zdjecie
from app.services.powiazania import powiaz
from app.services.zdjecia import BladZdjecia, usun_pliki, zapisz

zdjecia_bp = Blueprint("zdjecia", __name__)

LIMIT_NA_LISTE = 200


def katalog_zdjec() -> Path:
    katalog = Path(current_app.config["ZDJECIA_DIR"])
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def zdjecia_dla(**powiazanie) -> list[Zdjecie]:
    """Zdjecia przypiete do wskazanego elementu."""
    warunki = [getattr(Zdjecie, pole) == wartosc
               for pole, wartosc in powiazanie.items() if wartosc is not None]
    if not warunki:
        return []
    return list(db.session.scalars(
        select(Zdjecie).where(*warunki)
        .options(selectinload(Zdjecie.autor))
        .order_by(Zdjecie.utworzono.desc())
        .limit(LIMIT_NA_LISTE)
    ))


@zdjecia_bp.post("/api/zdjecia")
@login_required
def wyslij():
    """Przyjmij zdjecie z aparatu telefonu albo z dysku.

    Powiazanie podaje sie na jeden z trzech sposobow: `pomiar_id`, `raport_id`
    albo `dotyczy` (kod obiektu lub odcinka, jak wszedzie indziej w aplikacji).
    """
    plik = request.files.get("zdjecie")
    if plik is None or not plik.filename:
        return jsonify({"blad": "Nie przysłano pliku."}), 400

    zdjecie = Zdjecie(autor_id=current_user.id,
                      opis=(request.form.get("opis") or "").strip() or None)

    pomiar_id = request.form.get("pomiar_id", type=int)
    raport_id = request.form.get("raport_id", type=int)
    dotyczy = (request.form.get("dotyczy") or "").strip()

    if pomiar_id:
        if db.session.get(PomiarWykonawczy, pomiar_id) is None:
            return jsonify({"blad": "Nie ma takiego pomiaru."}), 404
        zdjecie.pomiar_id = pomiar_id
    if raport_id:
        if db.session.get(RaportDzienny, raport_id) is None:
            return jsonify({"blad": "Nie ma takiego raportu."}), 404
        zdjecie.raport_id = raport_id
    if dotyczy:
        obiekt, odcinek, blad = powiaz(dotyczy)
        if blad:
            return jsonify({"blad": blad}), 400
        zdjecie.segment_id = odcinek.id if odcinek else None
        zdjecie.obiekt_id = obiekt.id if (obiekt and odcinek is None) else None

    if not any((zdjecie.pomiar_id, zdjecie.raport_id,
                zdjecie.segment_id, zdjecie.obiekt_id)):
        return jsonify({
            "blad": "Podaj, czego dotyczy zdjęcie: pomiar_id, raport_id "
                    "albo dotyczy=D155."
        }), 400

    try:
        dane = zapisz(plik, katalog_zdjec())
    except BladZdjecia as blad:
        return jsonify({"blad": str(blad)}), 400

    for pole, wartosc in dane.items():
        setattr(zdjecie, pole, wartosc)
    db.session.add(zdjecie)
    db.session.commit()

    return jsonify({"zapisano": True, "zdjecie": zdjecie.to_dict()}), 201


def _podaj(zdjecie_id: int, miniatura: bool):
    zdjecie = db.session.get(Zdjecie, zdjecie_id)
    if zdjecie is None:
        abort(404, "Nie ma takiego zdjęcia.")

    wzgledna = (zdjecie.miniatura if miniatura else zdjecie.plik) or zdjecie.plik
    sciezka = katalog_zdjec() / wzgledna
    if not sciezka.exists():
        abort(404, "Plik zdjęcia zniknął z dysku.")

    odpowiedz = send_file(sciezka, mimetype="image/jpeg")
    # Zdjecie nie zmienia sie po zapisaniu, a na budowie kazdy zaoszczedzony
    # kilobajt to szybciej wczytana lista.
    odpowiedz.headers["Cache-Control"] = "private, max-age=604800"
    return odpowiedz


@zdjecia_bp.get("/zdjecia/<int:zdjecie_id>.jpg")
@login_required
def podaj(zdjecie_id: int):
    return _podaj(zdjecie_id, miniatura=False)


@zdjecia_bp.get("/zdjecia/<int:zdjecie_id>-mini.jpg")
@login_required
def podaj_miniature(zdjecie_id: int):
    return _podaj(zdjecie_id, miniatura=True)


@zdjecia_bp.get("/api/zdjecia")
@login_required
def lista():
    """Zdjecia powiazane ze wskazanym elementem."""
    dotyczy = (request.args.get("dotyczy") or "").strip()
    powiazanie: dict = {
        "pomiar_id": request.args.get("pomiar_id", type=int),
        "raport_id": request.args.get("raport_id", type=int),
    }
    if dotyczy:
        obiekt, odcinek, blad = powiaz(dotyczy)
        if blad:
            return jsonify({"blad": blad}), 400
        if odcinek is not None:
            powiazanie["segment_id"] = odcinek.id
        elif obiekt is not None:
            powiazanie["obiekt_id"] = obiekt.id

    return jsonify({"zdjecia": [z.to_dict() for z in zdjecia_dla(**powiazanie)]})


@zdjecia_bp.post("/zdjecia/<int:zdjecie_id>/usun")
@login_required
def usun(zdjecie_id: int):
    zdjecie = db.session.get(Zdjecie, zdjecie_id)
    if zdjecie is None:
        flash("Nie ma takiego zdjęcia.", "warning")
        return redirect(request.referrer or url_for("main.pulpit"))

    wlasne = zdjecie.autor_id == current_user.id
    if not (wlasne or current_user.jest_adminem):
        flash("Usunąć zdjęcie może jego autor albo administrator.", "danger")
        return redirect(request.referrer or url_for("main.pulpit"))

    usun_pliki(zdjecie, katalog_zdjec())
    db.session.delete(zdjecie)
    db.session.commit()
    flash("Zdjęcie usunięte.", "success")
    return redirect(request.referrer or url_for("main.pulpit"))
