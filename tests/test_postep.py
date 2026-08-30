"""Postep robot, rola montera i raporty dzienne.

Sedno tych testow to **uprawnienia**. Zglosic wykonanie moze kazdy, kto stoi
w wykopie, ale odbior jest decyzja kierownictwa - i to musi trzymac takze
wtedy, gdy ktos ominie interfejs i wysle zadanie wprost.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.models import (
    ETYKIETY,
    SCIEZKA,
    STANY_GOTOWE,
    RaportDzienny,
    Rola,
    Segment,
    StatusWykonania,
    User,
    ZmianaStatusu,
    nastepny_stan,
    poprzedni_stan,
    wolno_ustawic,
)

ODCINEK = ("Wyl101", "D155")
NAZWA_ODCINKA = "Wyl101-D155"


class Konto:
    """Namiastka uzytkownika - reguly uprawnien nie potrzebuja bazy."""

    def __init__(self, rola: Rola):
        self.rola = rola

    jest_adminem = property(lambda self: self.rola == Rola.ADMIN)
    moze_przydzielac = property(lambda self: self.rola in (Rola.ADMIN, Rola.KIEROWNIK))
    moze_odbierac = property(lambda self: self.rola in (Rola.ADMIN, Rola.KIEROWNIK))
    widzi_cudze_raporty = property(lambda self: self.rola != Rola.MONTER)


# ------------------------------------------------------------- sciezka


def test_sciezka_prowadzi_od_projektu_do_odbioru():
    assert SCIEZKA[0] is StatusWykonania.PROJEKT
    assert SCIEZKA[-1] is StatusWykonania.ODEBRANY
    assert nastepny_stan(StatusWykonania.PROJEKT) is StatusWykonania.WYTYCZONY
    assert nastepny_stan(StatusWykonania.ODEBRANY) is None
    assert poprzedni_stan(StatusWykonania.PROJEKT) is None
    assert poprzedni_stan(StatusWykonania.WYKONANY) is StatusWykonania.W_TRAKCIE


def test_wykonany_i_odebrany_to_dwa_rozne_stany():
    """Podzial na zgloszenie i odbior jest sednem calego etapu."""
    assert StatusWykonania.WYKONANY is not StatusWykonania.ODEBRANY
    assert set(STANY_GOTOWE) == {StatusWykonania.WYKONANY, StatusWykonania.ODEBRANY}


# ---------------------------------------------------------- uprawnienia


@pytest.mark.parametrize("rola", [Rola.MONTER, Rola.BRYGADZISTA, Rola.KIEROWNIK, Rola.ADMIN])
def test_kazdy_moze_zglosic_wykonanie(rola):
    """Odcinek uklada monter - i to on wie, kiedy jest gotowy."""
    wolno, _ = wolno_ustawic(Konto(rola), StatusWykonania.W_TRAKCIE,
                             StatusWykonania.WYKONANY)
    assert wolno


@pytest.mark.parametrize("rola,oczekiwane", [
    (Rola.MONTER, False),
    (Rola.BRYGADZISTA, False),
    (Rola.KIEROWNIK, True),
    (Rola.ADMIN, True),
])
def test_odbior_tylko_dla_kierownictwa(rola, oczekiwane):
    wolno, powod = wolno_ustawic(Konto(rola), StatusWykonania.WYKONANY,
                                 StatusWykonania.ODEBRANY)
    assert wolno is oczekiwane
    if not wolno:
        assert "kierownik" in powod.lower()


@pytest.mark.parametrize("rola,oczekiwane", [
    (Rola.MONTER, False), (Rola.BRYGADZISTA, False),
    (Rola.KIEROWNIK, True), (Rola.ADMIN, True),
])
def test_cofniecie_odbioru_tylko_dla_kierownictwa(rola, oczekiwane):
    """Odebrane roboty nie moze odkrecic ten, kto ich nie odbieral."""
    wolno, _ = wolno_ustawic(Konto(rola), StatusWykonania.ODEBRANY,
                             StatusWykonania.WYKONANY)
    assert wolno is oczekiwane


def test_ustawienie_tego_samego_stanu_nie_ma_sensu():
    wolno, powod = wolno_ustawic(Konto(Rola.ADMIN), StatusWykonania.WYKONANY,
                                 StatusWykonania.WYKONANY)
    assert not wolno
    assert "już jest" in powod


def test_monter_widzi_tylko_swoje_raporty():
    """Jedyna roznica monter - brygadzista."""
    assert Konto(Rola.MONTER).widzi_cudze_raporty is False
    assert Konto(Rola.BRYGADZISTA).widzi_cudze_raporty is True


def test_monter_nie_przydziela_zadan():
    assert Konto(Rola.MONTER).moze_przydzielac is False


def test_rola_monter_istnieje_w_bazie(db):
    """Typ enum w Postgresie trzeba rozszerzyc osobno - `create_all` tego nie robi."""
    from sqlalchemy import text

    wartosci = {w for (w,) in db.session.execute(text(
        "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = 'rola'"
    )).all()}
    assert "MONTER" in wartosci, "uruchom 'flask init-db' - brakuje ALTER TYPE rola"


# --------------------------------------------------- stan odcinka przez HTTP


@pytest.fixture()
def odcinek(db):
    if not db.session.scalar(select(func.count()).select_from(Segment)):
        pytest.skip("Baza pusta - uruchom 'flask import-wszystko'.")

    from app.services.powiazania import powiaz

    _, odc, _ = powiaz(NAZWA_ODCINKA)
    if odc is None:
        pytest.skip(f"Brak odcinka {NAZWA_ODCINKA}.")

    poczatkowy = odc.status
    db.session.execute(delete(ZmianaStatusu).where(ZmianaStatusu.segment_id == odc.id))
    odc.status = StatusWykonania.PROJEKT
    db.session.commit()

    yield odc

    db.session.execute(delete(ZmianaStatusu).where(ZmianaStatusu.segment_id == odc.id))
    odc.status = poczatkowy
    db.session.commit()


@pytest.fixture()
def konto_montera(db):
    """Konto montera zakladane na czas testu i po nim kasowane."""
    login = "pytest-monter"
    konto = db.session.scalar(select(User).where(User.login == login))
    if konto is None:
        konto = User(login=login, imie_nazwisko="Monter testowy")
        db.session.add(konto)
    konto.rola = Rola.MONTER
    konto.aktywny = True
    konto.ustaw_haslo("pytest-monter-haslo")
    db.session.commit()

    yield konto

    db.session.execute(delete(RaportDzienny).where(RaportDzienny.autor_id == konto.id))
    db.session.execute(delete(ZmianaStatusu).where(ZmianaStatusu.autor_id == konto.id))
    db.session.delete(konto)
    db.session.commit()


@pytest.fixture()
def klient_montera(app, konto_montera):
    c = app.test_client()
    odpowiedz = c.post("/login", data={"login": "pytest-monter",
                                       "haslo": "pytest-monter-haslo"})
    assert odpowiedz.status_code == 302, "monter nie zdolal sie zalogowac"
    return c


def test_pelna_sciezka_stanu_zapisuje_historie(klient, odcinek, db):
    for stan in ("WYTYCZONY", "W_TRAKCIE", "WYKONANY", "ODEBRANY"):
        odpowiedz = klient.post(f"/postep/{odcinek.id}/stan", data={"stan": stan})
        assert odpowiedz.status_code == 302

    db.session.expire_all()
    odc = db.session.get(Segment, odcinek.id)
    assert odc.status is StatusWykonania.ODEBRANY

    wpisy = list(db.session.scalars(
        select(ZmianaStatusu).where(ZmianaStatusu.segment_id == odcinek.id)
        .order_by(ZmianaStatusu.id)
    ))
    assert len(wpisy) == 4
    assert wpisy[0].poprzedni is StatusWykonania.PROJEKT
    assert wpisy[-1].nowy is StatusWykonania.ODEBRANY
    assert all(w.autor_id is not None for w in wpisy), "kazda zmiana ma miec podpis"


def test_monter_zglasza_ale_nie_odbiera(klient_montera, odcinek, db):
    for stan in ("WYTYCZONY", "W_TRAKCIE", "WYKONANY"):
        assert klient_montera.post(f"/postep/{odcinek.id}/stan",
                                   data={"stan": stan}).status_code == 302

    db.session.expire_all()
    assert db.session.get(Segment, odcinek.id).status is StatusWykonania.WYKONANY

    # Proba odbioru z pominieciem interfejsu.
    klient_montera.post(f"/postep/{odcinek.id}/stan", data={"stan": "ODEBRANY"})
    db.session.expire_all()
    assert db.session.get(Segment, odcinek.id).status is StatusWykonania.WYKONANY, (
        "monter odebral odcinek - regula uprawnien nie dziala po stronie serwera"
    )


def test_nieznany_stan_jest_odrzucany(klient, odcinek):
    assert klient.post(f"/postep/{odcinek.id}/stan",
                       data={"stan": "ZBUDOWANY_NA_OKO"}).status_code == 400


def test_api_odcinka_podaje_nastepny_krok(klient, odcinek):
    dane = klient.get(f"/api/postep/odcinek/{ODCINEK[0]}/{ODCINEK[1]}").get_json()
    assert dane["stan"] == "PROJEKT"
    assert dane["nastepny"]["stan"] == "WYTYCZONY"
    assert dane["nastepny"]["wolno"] is True
    assert dane["poprzedni"] is None


def test_monter_widzi_odmowe_odbioru_w_api(klient_montera, odcinek, db):
    odcinek.status = StatusWykonania.WYKONANY
    db.session.commit()

    dane = klient_montera.get(
        f"/api/postep/odcinek/{ODCINEK[0]}/{ODCINEK[1]}").get_json()
    assert dane["nastepny"]["stan"] == "ODEBRANY"
    assert dane["nastepny"]["wolno"] is False
    assert "kierownik" in dane["nastepny"]["powod"].lower()


def test_ostrzezenie_przy_zgloszeniu_bez_pomiarow(klient, odcinek):
    """Nie blokujemy, ale mowimy wprost, czego brakuje."""
    from app.blueprints.postep import ostrzezenia_przed_zgloszeniem

    uwagi = ostrzezenia_przed_zgloszeniem(odcinek, StatusWykonania.WYKONANY)
    assert any("ani jednego pomiaru" in u for u in uwagi)


def test_zgloszenie_wytyczenia_nie_wymaga_pomiarow(odcinek):
    from app.blueprints.postep import ostrzezenia_przed_zgloszeniem

    assert ostrzezenia_przed_zgloszeniem(odcinek, StatusWykonania.WYTYCZONY) == []


def test_ostrzezenie_o_pomiarach_poza_tolerancja(klient, odcinek, db):
    from app.blueprints.postep import ostrzezenia_przed_zgloszeniem
    from app.models import PomiarWykonawczy, RodzajPomiaru

    db.session.add(PomiarWykonawczy(
        segment_id=odcinek.id, rodzaj=RodzajPomiaru.DNO_KANALU,
        odleglosc_m=0.0, rzedna_zmierzona=float(odcinek.rzedna_dna_od) + 0.30,
    ))
    db.session.commit()
    try:
        uwagi = ostrzezenia_przed_zgloszeniem(odcinek, StatusWykonania.WYKONANY)
        assert any("poza tolerancją" in u for u in uwagi)
        assert any("0.3" in u for u in uwagi), "ostrzezenie ma podac liczbe"
    finally:
        db.session.execute(
            delete(PomiarWykonawczy).where(PomiarWykonawczy.segment_id == odcinek.id))
        db.session.commit()


def test_statystyki_postepu_sumuja_metry(klient, odcinek, db):
    from app.blueprints.postep import statystyki_postepu

    odcinek.status = StatusWykonania.ODEBRANY
    db.session.commit()

    staty = statystyki_postepu()
    assert staty["razem_m"] > 0
    assert staty["odebrane_m"] >= float(odcinek.dlugosc_m)
    assert 0 < staty["procent_odebrane"] <= 100
    assert sum(w["sztuk"] for w in staty["wg_stanu"].values()) == db.session.scalar(
        select(func.count()).select_from(Segment))


# ------------------------------------------------------- raporty dzienne


@pytest.fixture()
def czyste_raporty(db):
    db.session.execute(delete(RaportDzienny))
    db.session.commit()
    yield
    db.session.execute(delete(RaportDzienny))
    db.session.commit()


def test_raport_zapisuje_sie_z_metrami(klient, czyste_raporty, db):
    odpowiedz = klient.post("/raporty/dodaj", data={
        "dotyczy": NAZWA_ODCINKA, "opis": "ułożono 18 m Ø500",
        "metry": "18,5", "ludzi": "4", "sprzet": "koparka 15t",
        "pogoda": "deszcz", "przestoj_godziny": "1,5",
        "przestoj_powod": "brak rur na budowie",
    }, follow_redirects=True)
    assert odpowiedz.status_code == 200

    raport = db.session.scalar(select(RaportDzienny))
    assert float(raport.metry) == 18.5
    assert raport.ludzi == 4
    assert raport.byl_przestoj is True
    assert raport.czego_dotyczy == NAZWA_ODCINKA


def test_raport_bez_opisu_nie_przechodzi(klient, czyste_raporty, db):
    klient.post("/raporty/dodaj", data={"dotyczy": NAZWA_ODCINKA, "metry": "10"},
                follow_redirects=True)
    assert db.session.scalar(select(func.count()).select_from(RaportDzienny)) == 0


def test_raport_bez_odcinka_jest_dozwolony(klient, czyste_raporty, db):
    """Dowoz materialu tez jest praca, choc nie dotyczy zadnego odcinka."""
    klient.post("/raporty/dodaj", data={"opis": "dowóz rur, rozładunek"},
                follow_redirects=True)
    raport = db.session.scalar(select(RaportDzienny))
    assert raport is not None
    assert raport.czego_dotyczy == "—"


def test_raport_moze_od_razu_przestawic_stan(klient, odcinek, czyste_raporty, db):
    """Jeden formularz zamiast dwoch - to najczestszy ruch konca dnia."""
    klient.post("/raporty/dodaj", data={
        "dotyczy": NAZWA_ODCINKA, "opis": "wytyczono trasę", "stan": "WYTYCZONY",
    }, follow_redirects=True)

    db.session.expire_all()
    assert db.session.get(Segment, odcinek.id).status is StatusWykonania.WYTYCZONY
    zmiana = db.session.scalar(
        select(ZmianaStatusu).where(ZmianaStatusu.segment_id == odcinek.id))
    assert "raportu dziennego" in zmiana.uwagi


def test_monter_nie_odbierze_odcinka_przez_raport(klient_montera, odcinek,
                                                  czyste_raporty, db):
    """Furtka przez formularz raportu musi być zamknięta tak samo."""
    odcinek.status = StatusWykonania.WYKONANY
    db.session.commit()

    klient_montera.post("/raporty/dodaj", data={
        "dotyczy": NAZWA_ODCINKA, "opis": "poprawki", "stan": "ODEBRANY",
    }, follow_redirects=True)

    db.session.expire_all()
    assert db.session.get(Segment, odcinek.id).status is StatusWykonania.WYKONANY


def test_monter_widzi_wylacznie_swoje_raporty(klient, klient_montera,
                                              czyste_raporty, db):
    klient.post("/raporty/dodaj", data={"opis": "wpis administratora"},
                follow_redirects=True)
    klient_montera.post("/raporty/dodaj", data={"opis": "wpis montera"},
                        follow_redirects=True)

    monter = klient_montera.get("/api/raporty").get_json()["raporty"]
    assert len(monter) == 1
    assert monter[0]["opis"] == "wpis montera"

    admin = klient.get("/api/raporty").get_json()["raporty"]
    assert len(admin) == 2


def test_podsumowanie_tygodnia_pomija_stare_wpisy(klient, czyste_raporty, db):
    dawno = (date.today() - timedelta(days=30)).isoformat()
    klient.post("/raporty/dodaj", data={"opis": "stary wpis", "metry": "100",
                                        "data": dawno}, follow_redirects=True)
    klient.post("/raporty/dodaj", data={"opis": "dzisiejszy", "metry": "12,5",
                                        "ludzi": "3"}, follow_redirects=True)

    tydzien = klient.get("/api/raporty").get_json()["tydzien"]
    assert tydzien["metry"] == 12.5, "podsumowanie tygodnia zlicza stare wpisy"
    assert tydzien["dniowki"] == 3


def test_widoki_odpowiadaja(klient):
    assert klient.get("/postep").status_code == 200
    assert klient.get("/postep?stan=WYTYCZONY").status_code == 200
    assert klient.get("/raporty").status_code == 200
    assert klient.get(f"/raporty?dzien={date.today().isoformat()}").status_code == 200


def test_widoki_wymagaja_logowania(klient_anonim):
    for sciezka in ("/postep", "/raporty", "/api/raporty"):
        assert klient_anonim.get(sciezka).status_code == 302


# ------------------------------------------------------------- mapa


def test_warstwa_postepu_mowi_czego_nie_narysowala(klient, db):
    """Pokazanie 5 odcinkow z 40 i przemilczenie reszty byloby wprowadzaniem w blad."""
    from app.models import PlanSheet

    strona = db.session.scalar(
        select(PlanSheet).order_by(PlanSheet.nr_strony))
    if strona is None:
        pytest.skip("Brak arkuszy planu.")

    dane = klient.get(
        f"/api/mapa/postep/{strona.nr_strony}?wszystkie=1").get_json()
    assert "odcinki" in dane
    assert "nie_do_narysowania" in dane
    assert "legenda" in dane

    for odc in dane["odcinki"]:
        assert len(odc["punkty"]) == 2
        assert odc["kolor"].startswith("#")
        assert odc["etykieta"] in ETYKIETY.values()

    # Polowiczne maja jeden punkt i nazwe brakujacego obiektu.
    for odc in dane["polowiczne"]:
        assert len(odc["punkt"]) == 2
        assert odc["brakuje"]


def test_warstwa_postepu_dla_nieistniejacej_strony(klient):
    assert klient.get("/api/mapa/postep/999").status_code == 404
