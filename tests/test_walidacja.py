"""Kontrola jakosci danych i odpornosc importu na powtorzenie.

Trzy rzeczy, ktore audyt wykryl w dzialajacej bazie i ktore nie moga wrocic:

  1. import materialowy uruchamiany kilka razy dublowal komplet polaczen,
  2. rzedne pochodzace z rysunku nie odswiezaly sie przy ponownym imporcie,
  3. odcinki o dlugosci 0 m i spadku 314 promili szly do obliczen bez slowa.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import Connection, NetworkObject, Segment
from app.services.importer import _dodaj_polaczenie, _klucz_polaczenia
from app.services.walidacja import (
    KATEGORIE_BLOKUJACE,
    _sprawdz_obiekt,
    _sprawdz_odcinek,
    sprawdz_dane,
)


class PustyOdcinek:
    """Namiastka odcinka - regula ma dzialac bez bazy."""

    def __init__(self, dlugosc=None, spadek=None, rz_od=None, rz_do=None):
        self.dlugosc_m = dlugosc
        self.spadek_promile = spadek
        self.rzedna_dna_od = rz_od
        self.rzedna_dna_do = rz_do

    @property
    def spadek_wyliczony_promile(self):
        if self.rzedna_dna_od is None or self.rzedna_dna_do is None or not self.dlugosc_m:
            return None
        return round(abs(self.rzedna_dna_od - self.rzedna_dna_do) / self.dlugosc_m * 1000, 3)

    @property
    def rozjazd_spadku_promile(self):
        wyliczony = self.spadek_wyliczony_promile
        if wyliczony is None or self.spadek_promile is None:
            return None
        return round(abs(abs(self.spadek_promile) - wyliczony), 3)


# --------------------------------------------------------------- reguly


def kategorie(problemy):
    return {p.kategoria for p in problemy}


def test_odcinek_zerowy_jest_wylapywany():
    """Wyl103-Wp66 ma w dokumentacji dlugosc 0,00 m przy spadku 5 promili."""
    problemy = _sprawdz_odcinek(PustyOdcinek(0.0, 5.0, 83.50, 83.54), "Wyl103-Wp66")
    assert "ODCINEK_ZEROWY" in kategorie(problemy)


def test_brak_dlugosci_jest_wylapywany():
    problemy = _sprawdz_odcinek(PustyOdcinek(None, None), "Wp5-Wyl446")
    assert "ODCINEK_BEZ_DLUGOSCI" in kategorie(problemy)


def test_spadek_31_procent_jest_poza_zakresem():
    """Wyl253-Wp250: 1,09 m spadku na 3,5 m rury."""
    problemy = _sprawdz_odcinek(PustyOdcinek(3.5, 314.0, 84.75, 85.84), "Wyl253-Wp250")
    assert "SPADEK_POZA_ZAKRESEM" in kategorie(problemy)


def test_poprawny_odcinek_nie_budzi_zastrzezen():
    """Wyl101-D155 z profilu: 20,5 m, 3 promile, roznica rzednych 0,06 m."""
    problemy = _sprawdz_odcinek(PustyOdcinek(20.5, 3.0, 82.70, 82.76), "Wyl101-D155")
    assert problemy == []


def test_zaokraglenie_na_krotkim_odcinku_nie_jest_bledem():
    """Rzedne maja dokladnosc 1 cm, wiec na 3 m odcinku 0,01 m to juz 3,3 promila.

    Prog musi to tolerowac, inaczej polowa przykanalikow trafilaby do raportu.
    """
    problemy = _sprawdz_odcinek(PustyOdcinek(3.0, 5.0, 44.00, 44.02), "Wp1-Wyl1")
    assert "ROZJAZD_SPADKU" not in kategorie(problemy)


def test_powazny_rozjazd_spadku_jest_zglaszany():
    """D57-D59: rysunek mowi 73 promile, rzedne 9,2."""
    problemy = _sprawdz_odcinek(PustyOdcinek(20.0, 73.0, 50.00, 49.82), "D57-D59")
    assert "ROZJAZD_SPADKU" in kategorie(problemy)


def test_rozjazd_spadku_nie_blokuje_odcinka():
    """Rozjazd to powod do sprawdzenia, nie do uniewaznienia danych."""
    assert "ROZJAZD_SPADKU" not in KATEGORIE_BLOKUJACE


def test_niezmiennik_rzednych():
    ob = NetworkObject(kod="X1", rzedna_terenu_proj=83.81, rzedna_dna_kanalu=82.76,
                       zaglebienie=1.05)
    assert _sprawdz_obiekt(ob) == []

    ob.zaglebienie = 0.0
    problemy = _sprawdz_obiekt(ob)
    assert kategorie(problemy) == {"NIEZMIENNIK_RZEDNYCH"}


# ------------------------------------------------------- odsiew duplikatow


def test_klucz_polaczenia_zrownuje_puste_pola():
    """W Postgresie dwa NULL-e sa dla indeksu unikalnego rozne - stad coalesce."""
    a = Connection(obiekt_id=1, kierunek="DOPLYW")
    b = Connection(obiekt_id=1, kierunek="DOPLYW")
    assert _klucz_polaczenia(a) == _klucz_polaczenia(b)


def test_to_samo_wlaczenie_z_dwoch_profili_zapisuje_sie_raz():
    """Wlaczenie Wp466 do Wyl6 opisane jest i na profilu wylotu, i wpustu.

    To jedno polaczenie, nie dwa - i to wlasnie ono wywalalo import
    na indeksie unikalnym.
    """
    widziane: set = set()
    opis = "Proj. włączenie kanału Wp466 Ø200, Rz.d.=46.67"
    pierwsze = Connection(obiekt_id=19, obiekt_zrodlowy_kod="Wp466", dn_mm=200,
                          rzedna=46.67, kierunek="DOPLYW", opis=opis)
    drugie = Connection(obiekt_id=19, obiekt_zrodlowy_kod="Wp466", dn_mm=200,
                        rzedna=46.67, kierunek="DOPLYW", opis=opis)

    assert _dodaj_polaczenie(pierwsze, widziane) is True
    assert _dodaj_polaczenie(drugie, widziane) is False


# ----------------------------------------------------------- stan bazy


@pytest.fixture()
def baza_z_danymi(db):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta - uruchom najpierw 'flask import-wszystko'.")
    return db


def test_baza_nie_ma_zdublowanych_polaczen(baza_z_danymi):
    db = baza_z_danymi
    wszystkich = db.session.scalar(select(func.count()).select_from(Connection))
    unikalnych = len({
        _klucz_polaczenia(c) for c in db.session.scalars(select(Connection))
    })
    assert wszystkich == unikalnych, (
        f"{wszystkich - unikalnych} zdublowanych polaczen - "
        "import przestal byc odporny na powtorzenie"
    )


def test_baza_trzyma_niezmiennik_rzednych(baza_z_danymi):
    raport = sprawdz_dane(oznacz=False)
    lamiace = [p for p in raport.problemy if p.kategoria == "NIEZMIENNIK_RZEDNYCH"]
    assert lamiace == [], f"{len(lamiace)} obiektow lamie zaglebienie = teren - dno"


def test_podejrzane_odcinki_maja_podany_powod(baza_z_danymi):
    db = baza_z_danymi
    podejrzane = list(db.session.scalars(
        select(Segment).where(Segment.podejrzany.is_(True))
    ))
    assert podejrzane, "walidator nie oznaczyl zadnego odcinka - a znane sa cztery"
    for odc in podejrzane:
        assert odc.powod_podejrzenia, f"odcinek {odc.id} oznaczony bez podania powodu"


def test_spadek_z_rzednych_jest_zawsze_dodatni(baza_z_danymi):
    """Profile rysuje sie od wylotu w gore, ale spadek to wielkosc bez znaku."""
    db = baza_z_danymi
    for odc in db.session.scalars(select(Segment).limit(200)):
        wyliczony = odc.spadek_wyliczony_promile
        if wyliczony is not None:
            assert wyliczony >= 0, f"odcinek {odc.id} ma ujemny spadek {wyliczony}"


def test_kierunek_rysunku_jest_wystawiony(baza_z_danymi):
    db = baza_z_danymi
    odc = db.session.scalar(
        select(Segment).where(Segment.rzedna_dna_od.isnot(None),
                              Segment.rzedna_dna_do.isnot(None))
    )
    assert odc.kierunek_rysunku in ("z_pradem", "pod_prad")
    assert odc.to_dict()["kierunek_rysunku"] == odc.kierunek_rysunku
