"""Testy logowania, kont i zadan."""
import pytest

from tests.conftest import HASLO_TESTOWE, LOGIN_TESTOWY


# ---------------------------------------------------------------- ochrona


@pytest.mark.parametrize("sciezka", [
    "/", "/szukaj?q=D155", "/odcinki", "/obiekty", "/profile", "/osnowa",
    "/materialy", "/importy", "/niwelator/", "/niwelator/ciag-rur",
    "/mapa", "/zadania", "/panel/uzytkownicy", "/api/statystyki",
])
def test_bez_logowania_wszystko_przekierowuje(klient_anonim, sciezka):
    r = klient_anonim.get(sciezka)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_ekran_logowania_jest_dostepny_bez_sesji(klient_anonim):
    assert klient_anonim.get("/login").status_code == 200


def test_endpoint_zdrowia_zostaje_otwarty(klient_anonim):
    """Monitoring kontenera musi dzialac bez sesji."""
    assert klient_anonim.get("/api/zdrowie").status_code == 200


def test_zle_haslo_nie_wpuszcza(klient_anonim):
    r = klient_anonim.post("/login", data={"login": LOGIN_TESTOWY, "haslo": "nieprawidlowe"})
    assert r.status_code == 401


def test_nieznany_login_nie_wpuszcza(klient_anonim):
    r = klient_anonim.post("/login", data={"login": "nie-ma-takiego", "haslo": "cokolwiek"})
    assert r.status_code == 401


def test_poprawne_dane_wpuszczaja(klient_anonim):
    r = klient_anonim.post("/login", data={"login": LOGIN_TESTOWY, "haslo": HASLO_TESTOWE})
    assert r.status_code == 302
    assert klient_anonim.get("/").status_code == 200


def test_wylogowanie_odbiera_dostep(klient):
    assert klient.get("/").status_code == 200
    klient.get("/logout")
    assert klient.get("/").status_code == 302


def test_przekierowanie_po_zalogowaniu_tylko_wzgledne(klient_anonim):
    """Otwarte przekierowanie to klasyczna dziura - adres zewnetrzny ma byc odrzucony."""
    r = klient_anonim.post("/login?next=https://example.com/przejete",
                           data={"login": LOGIN_TESTOWY, "haslo": HASLO_TESTOWE})
    assert "example.com" not in r.headers.get("Location", "")


# ------------------------------------------------------------------ hasla


def test_haslo_nie_lezy_w_bazie_jawnie(app, konto_testowe):
    assert HASLO_TESTOWE not in konto_testowe.hash_hasla
    assert konto_testowe.sprawdz_haslo(HASLO_TESTOWE)
    assert not konto_testowe.sprawdz_haslo("cokolwiek innego")


def test_konto_wylaczone_nie_moze_wejsc(app, klient_anonim, konto_testowe, db):
    konto_testowe.aktywny = False
    db.session.commit()
    try:
        r = klient_anonim.post("/login", data={"login": LOGIN_TESTOWY, "haslo": HASLO_TESTOWE})
        assert r.status_code == 403
    finally:
        konto_testowe.aktywny = True
        db.session.commit()


# ----------------------------------------------------------------- panel


def test_admin_widzi_panel_kont(klient):
    html = klient.get("/panel/uzytkownicy").get_data(as_text=True)
    assert LOGIN_TESTOWY in html
    assert "Nowe konto" in html


def test_zakladanie_konta_i_logowanie_nowym(app, klient, klient_anonim, db):
    from sqlalchemy import select

    from app.models import User

    login = "test-brygadzista"
    db.session.query(User).filter(User.login == login).delete()
    db.session.commit()

    r = klient.post("/panel/uzytkownicy/dodaj", data={
        "login": login, "rola": "BRYGADZISTA", "haslo": "haslo-brygady-123",
    })
    assert r.status_code == 302

    nowy = db.session.scalar(select(User).where(User.login == login))
    assert nowy is not None and nowy.rola.value == "BRYGADZISTA"

    assert klient_anonim.post(
        "/login", data={"login": login, "haslo": "haslo-brygady-123"}
    ).status_code == 302

    db.session.delete(nowy)
    db.session.commit()


def test_nie_da_sie_zalozyc_konta_o_istniejacym_loginie(klient):
    r = klient.post("/panel/uzytkownicy/dodaj", data={"login": LOGIN_TESTOWY}, follow_redirects=True)
    assert "już istnieje" in r.get_data(as_text=True)


# ---------------------------------------------------------------- zadania


@pytest.mark.usefixtures("wymaga_danych")
def test_dodanie_zadania_globalnego(klient, db):
    from sqlalchemy import select

    from app.models import Task

    r = klient.post("/zadania/dodaj", data={
        "tytul": "TEST globalne — próba szczelności",
        "dotyczy": "D155", "priorytet": "WYSOKI",
    }, follow_redirects=True)
    assert r.status_code == 200

    z = db.session.scalar(select(Task).where(Task.tytul.like("TEST globalne%")))
    assert z is not None
    assert z.globalne is True
    assert z.czego_dotyczy == "D155"
    assert z.otwarte is True

    db.session.delete(z)
    db.session.commit()


@pytest.mark.usefixtures("wymaga_danych")
def test_zadanie_moze_wskazywac_odcinek(klient, db):
    from sqlalchemy import select

    from app.models import Task

    klient.post("/zadania/dodaj", data={
        "tytul": "TEST odcinek", "dotyczy": "Wyl101-D155",
    }, follow_redirects=True)
    z = db.session.scalar(select(Task).where(Task.tytul == "TEST odcinek"))
    assert z is not None and z.segment_id is not None
    assert z.czego_dotyczy == "Wyl101-D155"
    db.session.delete(z)
    db.session.commit()


def test_zmiana_statusu_zamyka_zadanie(klient, db):
    from sqlalchemy import select

    from app.models import Task

    klient.post("/zadania/dodaj", data={"tytul": "TEST status"}, follow_redirects=True)
    z = db.session.scalar(select(Task).where(Task.tytul == "TEST status"))
    klient.post(f"/zadania/{z.id}/status", data={"status": "ZROBIONE"})
    db.session.refresh(z)
    assert z.status.value == "ZROBIONE"
    assert z.otwarte is False
    assert z.zakonczono is not None
    db.session.delete(z)
    db.session.commit()


def test_zadanie_bez_tytulu_nie_powstaje(klient, db):
    from sqlalchemy import func, select

    from app.models import Task

    przed = db.session.scalar(select(func.count()).select_from(Task))
    klient.post("/zadania/dodaj", data={"tytul": "   "}, follow_redirects=True)
    assert db.session.scalar(select(func.count()).select_from(Task)) == przed


def test_lista_zadan_sie_renderuje(klient):
    html = klient.get("/zadania").get_data(as_text=True)
    assert "Nowe zadanie" in html
    assert "globalne" in html
