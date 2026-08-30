"""Zdjecia z budowy.

Rzedna mowi, ze wykop ma 1,73 m. Zdjecie mowi, ze na dnie stoi woda. Przy
sporze o odbior to zdjecie jest dowodem - dlatego testy pilnuja, zeby plik
faktycznie ladowal na dysku, a nie tylko wpis w bazie.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.models import Segment, Zdjecie
from app.services.zdjecia import BOK_ZDJECIA, BladZdjecia, zapisz

NAZWA_ODCINKA = "Wyl101-D155"


def obrazek(szerokosc=2400, wysokosc=1800, format_="JPEG", kolor=(120, 90, 60)):
    """Zdjecie udajace to z telefonu - duze i w orientacji poziomej."""
    from PIL import Image

    bufor = io.BytesIO()
    Image.new("RGB", (szerokosc, wysokosc), kolor).save(bufor, format_)
    bufor.seek(0)
    return bufor


class PlikZFormularza:
    """Namiastka `request.files[...]` - serwis nie potrzebuje Flaska."""

    def __init__(self, dane, filename="wykop.jpg", mimetype="image/jpeg"):
        self.stream = dane
        self.filename = filename
        self.mimetype = mimetype


# --------------------------------------------------------------- serwis


def test_zdjecie_jest_zmniejszane(tmp_path):
    """Zdjecie z telefonu ma 4000 px i kilkanascie MB. Do wykopu starczy 1600."""
    dane = zapisz(PlikZFormularza(obrazek(4000, 3000)), tmp_path)

    assert dane["szerokosc_px"] == BOK_ZDJECIA
    assert dane["wysokosc_px"] == pytest.approx(1200, abs=2)
    assert (tmp_path / dane["plik"]).exists()
    assert (tmp_path / dane["miniatura"]).exists()


def test_miniatura_jest_mniejsza_od_zdjecia(tmp_path):
    from PIL import Image

    from app.models.zdjecie import BOK_MINIATURY

    dane = zapisz(PlikZFormularza(obrazek()), tmp_path)
    with Image.open(tmp_path / dane["miniatura"]) as mini:
        assert max(mini.size) == BOK_MINIATURY


def test_male_zdjecie_nie_jest_powiekszane(tmp_path):
    """Powiekszanie tylko dodaje bajtow, nie informacji."""
    dane = zapisz(PlikZFormularza(obrazek(640, 480)), tmp_path)
    assert dane["szerokosc_px"] == 640


def test_png_i_webp_tez_przechodza(tmp_path):
    for format_, nazwa, typ in (("PNG", "a.png", "image/png"),
                                ("WEBP", "b.webp", "image/webp")):
        dane = zapisz(PlikZFormularza(obrazek(800, 600, format_), nazwa, typ), tmp_path)
        # Zapisujemy zawsze jako JPEG - jeden format to jedna sciezka kodu.
        assert dane["plik"].endswith(".jpg")


def test_plik_ktory_nie_jest_zdjeciem(tmp_path):
    with pytest.raises(BladZdjecia, match="nie jest zdjęcie"):
        zapisz(PlikZFormularza(io.BytesIO(b"to nie jest obrazek"),
                               "raport.pdf", "application/pdf"), tmp_path)


def test_uszkodzony_plik_daje_czytelny_komunikat(tmp_path):
    with pytest.raises(BladZdjecia, match="otworzyć"):
        zapisz(PlikZFormularza(io.BytesIO(b"\xff\xd8\xff garbage"),
                               "zepsute.jpg", "image/jpeg"), tmp_path)


def test_zdjecia_ladaja_w_katalogach_miesiecznych(tmp_path):
    """Jeden plaski katalog z tysiacem plikow jest nie do przeszukania recznie."""
    from datetime import date

    dane = zapisz(PlikZFormularza(obrazek(400, 300)), tmp_path)
    assert dane["plik"].startswith(date.today().strftime("%Y-%m") + "/")


def test_nazwy_plikow_sie_nie_powtarzaja(tmp_path):
    """Dwa zdjecia zrobione w tej samej sekundzie nie moga sie nadpisac."""
    nazwy = {zapisz(PlikZFormularza(obrazek(300, 200)), tmp_path)["plik"]
             for _ in range(5)}
    assert len(nazwy) == 5


# -------------------------------------------------------------- endpoint


@pytest.fixture()
def czyste_zdjecia(klient, db, app):
    katalog = Path(app.config["ZDJECIA_DIR"])

    def sprzataj():
        from app.services.zdjecia import usun_pliki

        for zdjecie in db.session.scalars(select(Zdjecie)):
            usun_pliki(zdjecie, katalog)
        db.session.execute(delete(Zdjecie))
        db.session.commit()

    sprzataj()
    yield klient
    sprzataj()


def wyslij(klient, **pola):
    dane = {"zdjecie": (obrazek(1200, 900), "wykop.jpg")}
    dane.update(pola)
    return klient.post("/api/zdjecia", data=dane,
                       content_type="multipart/form-data")


def test_wysylka_zapisuje_plik_i_wpis(czyste_zdjecia, db, app):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    odpowiedz = wyslij(czyste_zdjecia, dotyczy=NAZWA_ODCINKA,
                       opis="woda na dnie wykopu")
    assert odpowiedz.status_code == 201

    zdjecie = db.session.scalar(select(Zdjecie))
    assert zdjecie.opis == "woda na dnie wykopu"
    assert zdjecie.czego_dotyczy == NAZWA_ODCINKA
    assert (Path(app.config["ZDJECIA_DIR"]) / zdjecie.plik).exists(), (
        "wpis w bazie jest, a pliku na dysku nie ma"
    )


def test_zdjecie_musi_wiedziec_czego_dotyczy(czyste_zdjecia, db):
    """Zdjecie bez przypisania jest bezuzyteczne - za miesiac nikt nie odgadnie."""
    odpowiedz = wyslij(czyste_zdjecia)
    assert odpowiedz.status_code == 400
    assert "Podaj, czego dotyczy" in odpowiedz.get_json()["blad"]
    assert db.session.scalar(select(func.count()).select_from(Zdjecie)) == 0


def test_brak_pliku(czyste_zdjecia):
    odpowiedz = czyste_zdjecia.post("/api/zdjecia", data={"dotyczy": NAZWA_ODCINKA},
                                    content_type="multipart/form-data")
    assert odpowiedz.status_code == 400


def test_nieznany_odcinek(czyste_zdjecia):
    odpowiedz = wyslij(czyste_zdjecia, dotyczy="NIE-MA")
    assert odpowiedz.status_code == 400


def test_zdjecie_przy_pomiarze(czyste_zdjecia, db):
    from app.models import PomiarWykonawczy, RodzajPomiaru

    odcinek = db.session.scalar(select(Segment))
    if odcinek is None:
        pytest.skip("Baza pusta.")

    pomiar = PomiarWykonawczy(segment_id=odcinek.id, rodzaj=RodzajPomiaru.DNO_KANALU,
                              odleglosc_m=0.0, rzedna_zmierzona=82.7)
    db.session.add(pomiar)
    db.session.commit()
    try:
        assert wyslij(czyste_zdjecia, pomiar_id=pomiar.id).status_code == 201
        lista = czyste_zdjecia.get("/api/zdjecia",
                                   query_string={"pomiar_id": pomiar.id}).get_json()
        assert len(lista["zdjecia"]) == 1
    finally:
        db.session.execute(
            delete(PomiarWykonawczy).where(PomiarWykonawczy.id == pomiar.id))
        db.session.commit()


def test_podawanie_zdjecia_i_miniatury(czyste_zdjecia, db):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta.")
    wyslij(czyste_zdjecia, dotyczy=NAZWA_ODCINKA)
    zdjecie = db.session.scalar(select(Zdjecie))

    for adres in (f"/zdjecia/{zdjecie.id}.jpg", f"/zdjecia/{zdjecie.id}-mini.jpg"):
        odpowiedz = czyste_zdjecia.get(adres)
        assert odpowiedz.status_code == 200
        assert odpowiedz.mimetype == "image/jpeg"
        assert odpowiedz.data.startswith(b"\xff\xd8")       # naglowek JPEG


def test_usuniecie_kasuje_takze_plik(czyste_zdjecia, db, app):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta.")
    wyslij(czyste_zdjecia, dotyczy=NAZWA_ODCINKA)
    zdjecie = db.session.scalar(select(Zdjecie))
    sciezka = Path(app.config["ZDJECIA_DIR"]) / zdjecie.plik
    assert sciezka.exists()

    czyste_zdjecia.post(f"/zdjecia/{zdjecie.id}/usun", follow_redirects=True)
    assert not sciezka.exists(), "plik zostal na dysku po usunieciu wpisu"
    assert db.session.scalar(select(func.count()).select_from(Zdjecie)) == 0


def test_zdjecia_wymagaja_logowania(klient_anonim):
    assert klient_anonim.get("/zdjecia/1.jpg").status_code == 302
    assert klient_anonim.post("/api/zdjecia").status_code == 302


def test_limit_wielkosci_pliku_jest_ustawiony(app):
    """Bez limitu jedno zadanie moze zapchac dysk."""
    assert app.config["MAX_CONTENT_LENGTH"] > 0
    assert app.config["MAX_CONTENT_LENGTH"] <= 50 * 1024 * 1024


def test_zdjecia_nie_leza_w_kasowalnym_cache(app):
    """`data/exports` wolno skasowac w calosci. Zdjec z wykopu nie."""
    assert "exports" not in str(app.config["ZDJECIA_DIR"])
