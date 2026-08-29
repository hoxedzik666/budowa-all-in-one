"""Praca offline i kody QR na studnie.

Offline
-------
Narzedzie jest potrzebne przy wykopie, a tam zasieg bywa zaden. Service worker
(`app/static/service-worker.js`) trzyma w przegladarce statyki i ostatnio
ogladane dane, wiec raz otwarta karta odcinka otworzy sie ponownie bez sieci.

Skrypt musi byc podawany **z korzenia** (`/service-worker.js`), a nie z katalogu
statykow: przegladarka ogranicza jego zasieg do sciezki, z ktorej zostal pobrany.
Wydany spod `/static/` obslugiwalby tylko `/static/...` i byl bezuzyteczny.

Kody QR
-------
Studnia w terenie nie ma na sobie numeru. Naklejka z kodem QR zamienia
szukanie w dokumentacji na jedno zeskanowanie telefonem: kod prowadzi wprost
do karty obiektu z rzednymi, spadkiem i wykazem rur.
"""
from __future__ import annotations

from io import BytesIO

from flask import Blueprint, Response, abort, render_template, request, send_file, url_for
from sqlalchemy import select

from app.extensions import db
from app.models import NetworkObject, TypObiektu

pwa_bp = Blueprint("pwa", __name__)

MAX_KODOW_NA_ARKUSZ = 120


@pwa_bp.get("/service-worker.js")
def service_worker():
    """Skrypt offline podany z korzenia, zeby obejmowal cala aplikacje."""
    from pathlib import Path

    from flask import current_app

    plik = Path(current_app.root_path) / "static" / "service-worker.js"
    if not plik.exists():
        abort(404)
    odpowiedz = Response(plik.read_text(encoding="utf-8"),
                         mimetype="application/javascript")
    odpowiedz.headers["Service-Worker-Allowed"] = "/"
    # Bez tego przegladarka moglaby trzymac stara wersje skryptu i nie
    # zauwazyc zmiany strategii cache.
    odpowiedz.headers["Cache-Control"] = "no-cache"
    return odpowiedz


@pwa_bp.get("/offline")
def offline():
    """Strona pokazywana, gdy nie ma ani sieci, ani zapisanej kopii."""
    return render_template("pages/offline.html")


# ---------------------------------------------------------------- kody QR


@pwa_bp.get("/qr/<kod>.png")
def kod_qr(kod: str):
    """Kod QR prowadzacy do karty obiektu."""
    import qrcode

    obiekt = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
    if obiekt is None:
        abort(404, f"Nie ma obiektu {kod}.")

    rozmiar = min(max(request.args.get("px", 8, type=int), 3), 20)
    adres = url_for("szukaj.szukaj", q=obiekt.kod, _external=True)

    kod_obrazkowy = qrcode.QRCode(
        version=None,
        # Naklejka na studni bedzie zachlapana betonem i zakurzona - wyzsza
        # korekcja bledow pozwala odczytac kod mimo ubytkow.
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=rozmiar,
        border=2,
    )
    kod_obrazkowy.add_data(adres)
    kod_obrazkowy.make(fit=True)

    bufor = BytesIO()
    kod_obrazkowy.make_image(fill_color="black", back_color="white").save(bufor, "PNG")
    bufor.seek(0)
    return send_file(bufor, mimetype="image/png")


@pwa_bp.get("/qr")
def arkusz_kodow():
    """Arkusz kodow do wydruku i naklejenia na studnie."""
    szukaj = (request.args.get("szukaj") or "").strip()
    typ = (request.args.get("typ") or "STUDNIA").strip()

    q = select(NetworkObject)
    if szukaj:
        q = q.where(NetworkObject.kod.ilike(f"%{szukaj}%"))
    if typ and typ in TypObiektu.__members__:
        q = q.where(NetworkObject.typ == TypObiektu[typ])
    q = q.order_by(NetworkObject.kod).limit(MAX_KODOW_NA_ARKUSZ)

    return render_template(
        "pages/qr.html",
        obiekty=list(db.session.scalars(q)),
        szukaj=szukaj, typ=typ, typy=list(TypObiektu),
        limit=MAX_KODOW_NA_ARKUSZ,
    )
