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
from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

from app.extensions import db
from app.models import (
    NetworkObject,
    PlanAnchor,
    PlanGeoref,
    PlanLocation,
    PlanSheet,
    Segment,
    SurveyPoint,
)

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


# =====================================================================
#  Kafelki - plynne przyblizanie i przesuwanie arkusza
# =====================================================================

def _katalog_kafelkow() -> Path:
    katalog = Path(current_app.config["EXPORT_DIR"]) / "kafelki"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


@mapa_bp.get("/mapa/kafelek/<int:nr>/<int:z>/<int:x>/<int:y>.png")
def kafelek(nr: int, z: int, x: int, y: int):
    """Jeden kafelek 256 x 256 pikseli arkusza planu.

    Renderowany na zadanie i odkladany na dysk. Pierwsze wejscie na strone
    kosztuje ulamek sekundy (budowa listy wyswietlania), kolejne kafelki
    licza sie w kilkanascie milisekund.
    """
    from app.services import kafelki as k

    if not 0 <= z <= k.MAX_ZOOM or x < 0 or y < 0:
        abort(404)

    plik = _sciezka_planu()
    if not plik.exists():
        abort(404, "Brak pliku planów sytuacyjnych w katalogu docs/.")

    katalog = _katalog_kafelkow() / k.odcisk_pliku(plik)
    katalog.mkdir(parents=True, exist_ok=True)
    plik_kafelka = katalog / k.nazwa_kafelka(nr, z, x, y)

    if plik_kafelka.exists():
        dane = plik_kafelka.read_bytes()
    else:
        try:
            dane = k.renderuj_kafelek(plik, nr, z, x, y)
        except ValueError as blad:
            abort(404, str(blad))
        plik_kafelka.write_bytes(dane)

    odpowiedz = send_file(BytesIO(dane), mimetype="image/png")
    # Kafelek danej strony nigdy sie nie zmienia - odcisk pliku jest w sciezce
    # cache, wiec podmiana dokumentu i tak uniewazni adres.
    odpowiedz.headers["Cache-Control"] = "public, max-age=604800"
    return odpowiedz


@mapa_bp.get("/api/mapa/strona/<int:nr>")
def opis_strony(nr: int):
    """Wszystko, czego przegladarka potrzebuje, zeby narysowac mape."""
    from app.services import kafelki as k

    strony = zapewnij_strony()
    strona = next((s for s in strony if s.nr_strony == nr), None)
    if strona is None:
        return jsonify({"blad": f"Nie ma strony {nr}."}), 404

    szerokosc = float(strona.szerokosc_pt or 0)
    wysokosc = float(strona.wysokosc_pt or 0)
    georef = strona.georef

    return jsonify({
        "nr_strony": strona.nr_strony,
        "szerokosc_pt": szerokosc,
        "wysokosc_pt": wysokosc,
        "skala": strona.skala,
        "metry_na_punkt": round(k.METRY_NA_PUNKT * (strona.skala or 1000) / 1000.0, 6),
        "max_zoom": k.MAX_ZOOM,
        "bok_kafelka": k.BOK_KAFELKA,
        "georef": georef.to_dict() if georef else None,
        "kotwice": [kot.to_dict() for kot in strona.kotwice],
        "lokalizacje": [
            lok.to_dict() for lok in db.session.scalars(
                select(PlanLocation).where(PlanLocation.strona_id == strona.id)
                .options(selectinload(PlanLocation.obiekt))
            )
        ],
    })


# =====================================================================
#  Georeferencja - zwiazanie arkusza z ukladem PL-2000/5
# =====================================================================

def _przelicz_georef(strona: PlanSheet) -> dict:
    """Przelicz przeksztalcenie z kotwic zapisanych dla arkusza.

    Wywolywane po kazdej zmianie kotwic. Ponizej dwoch kotwic po prostu
    kasujemy przeksztalcenie - lepiej brak wyniku niz wynik zmyslony.
    """
    from app.services.georef import dopasuj

    kotwice = [kot.kotwica() for kot in strona.kotwice]
    if len(kotwice) < 2:
        if strona.georef is not None:
            db.session.delete(strona.georef)
            db.session.commit()
        return {"georef": None, "powod": "Potrzebne są co najmniej dwie kotwice."}

    przeksztalcenie = dopasuj(kotwice)
    zapis = strona.georef or PlanGeoref(strona_id=strona.id)
    (zapis.ey_x, zapis.ey_y, zapis.ey_0,
     zapis.nx_x, zapis.nx_y, zapis.nx_0) = przeksztalcenie.to_dict()["wspolczynniki"]
    zapis.skala_m_na_pt = przeksztalcenie.skala_m_na_pt
    zapis.obrot_stopnie = przeksztalcenie.obrot_stopnie
    zapis.rmse_m = przeksztalcenie.rmse_m
    zapis.liczba_kotwic = przeksztalcenie.liczba_kotwic
    db.session.add(zapis)
    db.session.commit()
    return {"georef": zapis.to_dict(), "powod": None}


@mapa_bp.post("/api/mapa/kotwica")
def dodaj_kotwice():
    """Wskaz na arkuszu punkt o znanych wspolrzednych.

    Zwykle jest to reper z osnowy - wtedy wystarczy jego nazwa, a wspolrzedne
    program bierze z bazy. Mozna tez podac X i Y wprost.
    """
    dane = request.get_json(silent=True) or {}
    strona = db.session.get(PlanSheet, int(dane.get("strona_id", 0)))
    if strona is None:
        return jsonify({"blad": "Nie ma takiej strony planu."}), 404

    try:
        x_pt, y_pt = float(dane["x_pt"]), float(dane["y_pt"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"blad": "Wymagane: x_pt, y_pt."}), 400

    nazwa = (dane.get("reper") or dane.get("nazwa") or "").strip()
    punkt = None
    if nazwa:
        punkt = db.session.scalar(
            select(SurveyPoint).where(func.lower(SurveyPoint.nazwa) == nazwa.lower())
        )

    if punkt is not None:
        x_gis, y_gis = float(punkt.x), float(punkt.y)
        nazwa = punkt.nazwa
    else:
        try:
            x_gis, y_gis = float(dane["x_gis"]), float(dane["y_gis"])
        except (KeyError, TypeError, ValueError):
            return jsonify({
                "blad": f"Nie znam repera „{nazwa}”. Podaj nazwę punktu z osnowy "
                        "albo współrzędne X i Y wprost."
            }), 400
        nazwa = nazwa or f"punkt {len(strona.kotwice) + 1}"

    istniejaca = db.session.scalar(
        select(PlanAnchor).where(PlanAnchor.strona_id == strona.id,
                                 PlanAnchor.nazwa == nazwa)
    )
    kotwica = istniejaca or PlanAnchor(strona_id=strona.id, nazwa=nazwa)
    kotwica.x_pt, kotwica.y_pt = x_pt, y_pt
    kotwica.x_gis, kotwica.y_gis = x_gis, y_gis
    kotwica.punkt_id = punkt.id if punkt else None
    db.session.add(kotwica)
    db.session.commit()

    db.session.refresh(strona)
    wynik = _przelicz_georef(strona)
    return jsonify({
        "zapisano": True,
        "kotwica": kotwica.to_dict(),
        "kotwice": [k.to_dict() for k in strona.kotwice],
        **wynik,
    })


@mapa_bp.delete("/api/mapa/kotwica/<int:kotwica_id>")
def usun_kotwice(kotwica_id: int):
    kotwica = db.session.get(PlanAnchor, kotwica_id)
    if kotwica is None:
        return jsonify({"blad": "Nie ma takiej kotwicy."}), 404
    strona = kotwica.strona
    db.session.delete(kotwica)
    db.session.commit()
    db.session.refresh(strona)
    return jsonify({"usunieto": True, "kotwice": [k.to_dict() for k in strona.kotwice],
                    **_przelicz_georef(strona)})


@mapa_bp.get("/api/mapa/wspolrzedne/<int:nr>")
def wspolrzedne(nr: int):
    """Punkt rysunku -> wspolrzedne w terenie. Dziala po georeferencji."""
    strona = db.session.scalar(select(PlanSheet).where(PlanSheet.nr_strony == nr))
    if strona is None or strona.georef is None:
        return jsonify({"blad": "Ten arkusz nie jest jeszcze związany z terenem."}), 404
    try:
        x_pt, y_pt = float(request.args["x_pt"]), float(request.args["y_pt"])
    except (KeyError, ValueError):
        return jsonify({"blad": "Wymagane: x_pt, y_pt."}), 400

    x_gis, y_gis = strona.georef.przeksztalcenie().na_teren(x_pt, y_pt)
    return jsonify({"x_gis": x_gis, "y_gis": y_gis, "uklad": strona.georef.uklad})


@mapa_bp.get("/api/mapa/repery/<int:nr>")
def repery_na_arkuszu(nr: int):
    """Repery z osnowy naniesione na arkusz - bez klikania, z przeksztalcenia.

    To jest wlasciwy powod, dla ktorego robimy georeferencje: dopiero majac
    repery na planie da sie odpowiedziec na pytanie "z ktorego repera nawiazac
    sie przy tej studni".
    """
    strona = db.session.scalar(select(PlanSheet).where(PlanSheet.nr_strony == nr))
    if strona is None or strona.georef is None:
        return jsonify({"dostepne": False, "repery": [],
                        "powod": "Ten arkusz nie jest jeszcze związany z terenem."})

    przeksztalcenie = strona.georef.przeksztalcenie()
    szerokosc = float(strona.szerokosc_pt or 0)
    wysokosc = float(strona.wysokosc_pt or 0)
    margines = 200.0

    wynik = []
    for punkt in db.session.scalars(
        select(SurveyPoint).where(SurveyPoint.x.isnot(None), SurveyPoint.y.isnot(None))
    ):
        x_pt, y_pt = przeksztalcenie.na_rysunek(float(punkt.x), float(punkt.y))
        # Osnowa obejmuje cala budowe; na tym arkuszu lezy tylko czesc punktow.
        if not (-margines <= x_pt <= szerokosc + margines
                and -margines <= y_pt <= wysokosc + margines):
            continue
        wynik.append({"nazwa": punkt.nazwa, "x_pt": x_pt, "y_pt": y_pt,
                      "h": float(punkt.h) if punkt.h is not None else None,
                      "x_gis": float(punkt.x), "y_gis": float(punkt.y)})

    return jsonify({"dostepne": True, "repery": sorted(wynik, key=lambda r: r["nazwa"]),
                    "powod": None})


# =====================================================================
#  Wycieta siec wektorowa i eksport
# =====================================================================

def _katalog_sieci() -> Path:
    return Path(current_app.config["EXPORT_DIR"]) / "siec"


def wczytaj_siec(nr_strony: int):
    """Wynik konwertera dla jednej strony albo None, jesli jeszcze go nie ma."""
    from app.services.plan_eksport import z_json

    plik = _katalog_sieci() / f"strona-{nr_strony:02d}.json"
    if not plik.exists():
        return None
    return z_json(plik.read_text(encoding="utf-8"))


def _odwzorowanie(strona: PlanSheet):
    from app.services.plan_eksport import Odwzorowanie

    return Odwzorowanie(
        przeksztalcenie=strona.georef.przeksztalcenie() if strona.georef else None,
        skala=strona.skala or 1000,
    )


@mapa_bp.get("/api/mapa/siec/<int:nr>")
def siec_strony(nr: int):
    """Polilinie wyciete z rysunku - do narysowania jako warstwa na mapie."""
    siec = wczytaj_siec(nr)
    if siec is None:
        return jsonify({
            "dostepne": False, "polilinie": [], "etykiety": [],
            "powod": "Ta strona nie została jeszcze przekonwertowana. "
                     "Uruchom: flask konwertuj-plany",
        })
    return jsonify({
        "dostepne": True,
        "powod": None,
        **siec.podsumowanie(),
        "polilinie": [
            {"punkty": p.punkty, "dlugosc_m": p.dlugosc_m(siec.skala)}
            for p in siec.polilinie
        ],
        "etykiety": [e.to_dict() for e in siec.etykiety],
    })


@mapa_bp.get("/mapa/eksport/<int:nr>.<format_>")
def eksport_sieci(nr: int, format_: str):
    """Wyciete polilinie w formacie dla geodety albo projektanta."""
    from app.services.plan_eksport import FORMATY, zapisz

    if format_ not in FORMATY:
        abort(404, f"Nie znam formatu {format_}. Dostępne: {', '.join(sorted(FORMATY))}.")

    siec = wczytaj_siec(nr)
    if siec is None:
        abort(404, "Ta strona nie została jeszcze przekonwertowana "
                   "(flask konwertuj-plany).")

    strona = db.session.scalar(select(PlanSheet).where(PlanSheet.nr_strony == nr))
    if strona is None:
        abort(404, f"Nie ma strony {nr}.")

    tresc, mime, rozszerzenie = zapisz(siec, _odwzorowanie(strona), format_)
    return send_file(
        BytesIO(tresc.encode("utf-8")), mimetype=mime, as_attachment=True,
        download_name=f"plan-strona-{nr:02d}{rozszerzenie}",
    )


@mapa_bp.get("/mapa/eksport/<int:nr>.pgw")
def plik_swiata_strony(nr: int):
    """Plik swiata do wyrenderowanego PNG - otwiera go w QGIS na swoim miejscu."""
    from app.services.georef import plik_swiata

    strona = db.session.scalar(select(PlanSheet).where(PlanSheet.nr_strony == nr))
    if strona is None or strona.georef is None:
        abort(404, "Ten arkusz nie jest jeszcze związany z terenem — "
                   "wskaż dwie kotwice na mapie.")
    dpi = min(max(request.args.get("dpi", DPI_PODGLAD, type=int), 30), 300)
    tresc = plik_swiata(strona.georef.przeksztalcenie(), dpi)
    return send_file(
        BytesIO(tresc.encode("ascii")), mimetype="text/plain", as_attachment=True,
        download_name=f"plan-strona-{nr:02d}.pgw",
    )
