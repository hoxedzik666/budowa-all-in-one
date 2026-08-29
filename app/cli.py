"""Komendy CLI: przygotowanie bazy i import dokumentacji projektowej."""
from __future__ import annotations

import json
import time
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import func, select, text

from app.extensions import db


def register_cli(app: Flask) -> None:

    @app.cli.command("db-wait")
    @click.option("--prob", default=40, help="Ile prob polaczenia z baza.")
    def db_wait(prob: int) -> None:
        """Czekaj az Postgres bedzie gotowy."""
        for i in range(1, prob + 1):
            try:
                db.session.execute(text("SELECT 1"))
                db.session.commit()
                click.echo(f"Baza gotowa (proba {i}).")
                return
            except Exception as exc:  # noqa: BLE001
                db.session.rollback()
                click.echo(f"  [{i}/{prob}] baza jeszcze nie odpowiada: {type(exc).__name__}")
                time.sleep(2)
        raise SystemExit("Nie udalo sie polaczyc z baza.")

    @app.cli.command("init-db")
    def init_db() -> None:
        """Utworz tabele i dolóż brakujace kolumny."""
        from app.services.schemat import dostosuj_schemat

        db.create_all()
        zmiany = dostosuj_schemat()
        for zmiana in zmiany:
            click.echo(f"  schemat: {zmiana}")
        click.echo("Schemat bazy gotowy.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Skasowac wszystkie tabele i utworzyc od nowa?")
    def reset_db() -> None:
        db.drop_all()
        db.create_all()
        click.echo("Baza wyczyszczona i odtworzona.")

    # ------------------------------------------------------------ importy

    def _sciezka(podana: str | None, domyslna: str) -> Path:
        if podana:
            return Path(podana)
        return Path(app.config["DOCS_DIR"]) / domyslna

    @app.cli.command("import-osnowa")
    @click.argument("plik", required=False)
    def import_osnowa(plik: str | None) -> None:
        """Wczytaj punkty osnowy geodezyjnej (repery)."""
        from app.services.importer import importuj_osnowe

        sciezka = _sciezka(plik, app.config["OSNOWA_TXT"])
        click.echo(f"Import osnowy z {sciezka} ...")
        bieg = importuj_osnowe(sciezka)
        click.echo(f"  punktow: {bieg.liczba_obiektow}, ostrzezen: {bieg.liczba_ostrzezen}")

    @app.cli.command("import-profile")
    @click.argument("plik", required=False)
    @click.option("--bez-czyszczenia", is_flag=True, help="Nie kasuj poprzedniego importu.")
    def import_profile(plik: str | None, bez_czyszczenia: bool) -> None:
        """Rozbij "Profile Scalone.pdf" na obiekty i odcinki, zapisz do bazy."""
        from app.services.importer import importuj_profile

        sciezka = _sciezka(plik, app.config["PROFILE_PDF"])
        click.echo(f"Import profili z {sciezka} ...")
        bieg = importuj_profile(sciezka, wyczysc=not bez_czyszczenia)
        click.echo(f"  profili:  {bieg.liczba_profili}")
        click.echo(f"  obiektow: {bieg.liczba_obiektow}")
        click.echo(f"  odcinkow: {bieg.liczba_odcinkow}")
        click.echo(f"  ostrzezen: {bieg.liczba_ostrzezen}")
        click.echo(f"  statystyki: {json.dumps(bieg.statystyki, ensure_ascii=False)}")
        if not bez_czyszczenia:
            click.echo("\n  UWAGA: import profili zerowal rzedne pochodzace z rysunku.")
            click.echo("  Uruchom teraz 'flask import-xlsx', zeby wrocily uzupelnienia")
            click.echo("  z arkusza materialowego (albo od razu 'flask import-wszystko').")

    @app.cli.command("import-xlsx")
    @click.argument("plik", required=False)
    def import_xlsx(plik: str | None) -> None:
        """Wczytaj arkusze Studnie / Wpusty / Wyloty / RURY i porownaj z PDF."""
        from app.services.xlsx_importer import importuj_xlsx

        sciezka = _sciezka(plik, app.config["MATERIAL_XLSX"])
        click.echo(f"Import arkusza z {sciezka} ...")
        bieg = importuj_xlsx(sciezka)
        click.echo(f"  statystyki: {json.dumps(bieg.statystyki, ensure_ascii=False)}")
        click.echo(f"  rozbieznosci PDF vs XLSX: {bieg.liczba_ostrzezen}")

    @app.cli.command("import-wszystko")
    def import_wszystko() -> None:
        """Pelny import: osnowa -> profile -> arkusz materialowy.

        Kolejnosc nie jest dowolna: import profili czysci rzedne pochodzace
        z rysunku, a arkusz materialowy uzupelnia to, czego rysunek nie podaje.
        Odwrotna kolejnosc zgubilaby uzupelnienia.
        """
        from app.services.importer import importuj_osnowe, importuj_profile
        from app.services.schemat import dostosuj_schemat
        from app.services.xlsx_importer import importuj_xlsx

        docs = Path(app.config["DOCS_DIR"])
        db.create_all()
        dostosuj_schemat()
        for etykieta, funkcja, nazwa in (
            ("osnowa", importuj_osnowe, app.config["OSNOWA_TXT"]),
            ("profile", importuj_profile, app.config["PROFILE_PDF"]),
            ("material", importuj_xlsx, app.config["MATERIAL_XLSX"]),
        ):
            sciezka = docs / nazwa
            if not sciezka.exists():
                click.echo(f"  POMINIETO {etykieta}: brak pliku {sciezka}")
                continue
            click.echo(f"--- {etykieta}: {sciezka.name}")
            bieg = funkcja(sciezka)
            click.echo(f"    ostrzezen: {bieg.liczba_ostrzezen} | {bieg.statystyki}")
        _podsumowanie()

    @app.cli.command("audyt-danych")
    @click.option("--kategoria", default="", help="Pokaz tylko jedna kategorie problemow.")
    @click.option("--ile", default=15, show_default=True, help="Ile przykladow na kategorie.")
    @click.option("--oznacz/--tylko-raport", default=True,
                  help="Czy zapisac flage 'podejrzany' na odcinkach.")
    def audyt_danych(kategoria: str, ile: int, oznacz: bool) -> None:
        """Sprawdz, czy dane w bazie trzymaja sie kupy.

        Nie poprawia liczb - pokazuje, ktorym nie wolno ufac i dlaczego.
        """
        from app.services.walidacja import sprawdz_dane

        raport = sprawdz_dane(oznacz=oznacz)

        click.echo("\n=== BRAKI I STAN DANYCH ===")
        for klucz, wartosc in raport.statystyki.items():
            click.echo(f"  {klucz:26} {wartosc}")

        click.echo("\n=== PROBLEMY ===")
        if not raport.problemy:
            click.echo("  Zadnych. Dane sa spojne.")
            return

        wg_kategorii: dict[str, list] = {}
        for p in raport.problemy:
            wg_kategorii.setdefault(p.kategoria, []).append(p)

        for nazwa, lista in sorted(wg_kategorii.items(), key=lambda x: -len(x[1])):
            if kategoria and nazwa != kategoria.upper():
                continue
            click.echo(f"\n  {nazwa}  ({len(lista)})")
            for p in lista[:ile]:
                click.echo(f"    {p.czego_dotyczy:16} {p.opis}")
            if len(lista) > ile:
                click.echo(f"    ... i jeszcze {len(lista) - ile}")

        click.echo(f"\n  Razem problemow: {len(raport.problemy)}")
        click.echo("  Pelna lista jest tez na /importy po kazdym imporcie.")

    @app.cli.command("ocr-plany")
    @click.argument("plik", required=False)
    @click.option("--strony", default="", help="Np. 7,9,13. Puste = wszystkie.")
    @click.option("--dpi", default=300, show_default=True)
    @click.option("--zapisz/--tylko-raport", default=False,
                  help="Czy zapisac znalezione pozycje do bazy.")
    def ocr_plany(plik, strony, dpi, zapisz):
        """Sprobuj odzyskac etykiety z planow sytuacyjnych (OCR).

        Etykiety na planach sa zamienione na krzywe wektorowe. OCR jest proba
        ich odzyskania - skutecznosc jest niska i kazdy wynik ma zapisany
        poziom pewnosci. Domyslnie komenda tylko raportuje, nie zapisuje.
        """
        from sqlalchemy import select

        from app.models import NetworkObject, PlanLocation, PlanSheet
        from app.services.plan_ocr import ocr_planow, tesseract_dostepny

        ok, info = tesseract_dostepny()
        if not ok:
            raise SystemExit(f"Tesseract niedostepny: {info}")
        click.echo(f"tesseract {info}")

        sciezka = _sciezka(plik, "Plany sytuacyjne Scalone.pdf")
        if not sciezka.exists():
            raise SystemExit(f"Brak pliku {sciezka}")

        numery = [int(x) for x in strony.split(",") if x.strip()] or None
        kody = {o.kod for o in db.session.scalars(select(NetworkObject))}
        click.echo(f"Znanych kodow w bazie: {len(kody)}")
        click.echo("Uwaga: OCR gestego rysunku CAD bywa bezskuteczny - to proba, nie pewnik.")

        wyniki = ocr_planow(sciezka, kody, numery, dpi)
        razem = 0
        for w in wyniki:
            click.echo(f"  s.{w.nr_strony:2d} 1:{w.skala}  tokenow={w.surowych_tokenow:6d} "
                       f"dopasowanych={len(w.trafienia):3d}")
            for t in w.trafienia[:10]:
                click.echo(f"       {t.kod:9} pewnosc={t.pewnosc:5.1f} "
                           f"x={t.x_pt:7.1f} y={t.y_pt:7.1f} ocr={t.tekst!r}")
            razem += len(w.trafienia)

            if zapisz and w.trafienia:
                strona = db.session.scalar(
                    select(PlanSheet).where(PlanSheet.plik == sciezka.name,
                                            PlanSheet.nr_strony == w.nr_strony))
                if strona is None:
                    strona = PlanSheet(plik=sciezka.name, nr_strony=w.nr_strony,
                                       szerokosc_pt=w.szerokosc_pt, wysokosc_pt=w.wysokosc_pt,
                                       skala=w.skala)
                    db.session.add(strona)
                    db.session.flush()
                strona.etykiet_ocr = w.surowych_tokenow
                strona.dopasowanych = len(w.trafienia)
                for t in w.trafienia:
                    ob = db.session.scalar(
                        select(NetworkObject).where(NetworkObject.kod == t.kod))
                    if ob is None:
                        continue
                    istniejaca = db.session.scalar(
                        select(PlanLocation).where(PlanLocation.obiekt_id == ob.id,
                                                   PlanLocation.strona_id == strona.id))
                    if istniejaca is not None and istniejaca.zweryfikowane:
                        continue   # recznie wskazana pozycja ma pierwszenstwo
                    lok = istniejaca or PlanLocation(obiekt_id=ob.id, strona_id=strona.id)
                    lok.x_pt, lok.y_pt = t.x_pt, t.y_pt
                    lok.pewnosc, lok.tekst_ocr, lok.zrodlo = t.pewnosc, t.tekst, "OCR"
                    db.session.add(lok)
                db.session.commit()

        click.echo(f"Razem dopasowanych etykiet: {razem}")
        if not razem:
            click.echo(
                "OCR nie odczytal ani jednej etykiety. Napisy na planach sa zamienione "
                "na krzywe i leza pod katem na gestym rysunku - w tej dokumentacji "
                "trzeba wskazac pozycje recznie w przegladarce planow (/mapa)."
            )

    # ------------------------------------------------------------- konta

    @app.cli.command("utworz-admina")
    @click.option("--login", default="budowa-adm", show_default=True)
    @click.option("--haslo", default="", help="Puste = wygeneruj losowe.")
    def utworz_admina(login: str, haslo: str) -> None:
        """Utworz konto administratora i zapisz haslo do .env."""
        import secrets

        from sqlalchemy import func

        from app.models import Rola, User

        db.create_all()
        istnieje = db.session.scalar(
            select(User).where(func.lower(User.login) == login.lower()))
        if istnieje is not None:
            click.echo(f"Konto {login} juz istnieje. Uzyj: flask zmien-haslo {login}")
            return

        haslo = haslo or secrets.token_urlsafe(14)
        uzytkownik = User(login=login, rola=Rola.ADMIN,
                          imie_nazwisko="Administrator budowy")
        uzytkownik.ustaw_haslo(haslo)
        db.session.add(uzytkownik)
        db.session.commit()

        _zapisz_do_env("ADMIN_LOGIN", login)
        _zapisz_do_env("ADMIN_HASLO", haslo)

        click.echo("")
        click.echo("=" * 58)
        click.echo(f"  KONTO ADMINISTRATORA UTWORZONE")
        click.echo(f"  login:  {login}")
        click.echo(f"  haslo:  {haslo}")
        click.echo("=" * 58)
        click.echo("  Haslo zapisano rowniez w pliku .env (jest w .gitignore).")
        click.echo("  W bazie lezy wylacznie skrot - jawnego hasla nie da sie odczytac.")
        click.echo("")

    @app.cli.command("zmien-haslo")
    @click.argument("login")
    @click.option("--haslo", default="", help="Puste = wygeneruj losowe.")
    def zmien_haslo(login: str, haslo: str) -> None:
        """Ustaw nowe haslo dla istniejacego konta."""
        import secrets

        from sqlalchemy import func

        from app.models import User

        uzytkownik = db.session.scalar(
            select(User).where(func.lower(User.login) == login.lower()))
        if uzytkownik is None:
            raise SystemExit(f"Nie ma konta {login}.")
        haslo = haslo or secrets.token_urlsafe(14)
        uzytkownik.ustaw_haslo(haslo)
        db.session.commit()
        click.echo(f"Nowe haslo dla {login}: {haslo}")

    @app.cli.command("lista-kont")
    def lista_kont() -> None:
        """Wypisz konta i ich role."""
        from app.models import User

        for u in db.session.scalars(select(User).order_by(User.login)):
            stan = "aktywne" if u.aktywny else "WYLACZONE"
            ostatnie = (u.ostatnie_logowanie.strftime("%Y-%m-%d %H:%M")
                        if u.ostatnie_logowanie else "nigdy")
            click.echo(f"  {u.login:20} {u.rola.value:12} {stan:10} ostatnio: {ostatnie}")

    @app.cli.command("statystyki")
    def statystyki() -> None:
        """Co siedzi w bazie."""
        _podsumowanie()

    @app.cli.command("pokaz-odcinek")
    @click.argument("od")
    @click.argument("do_")
    def pokaz_odcinek(od: str, do_: str) -> None:
        """Wypisz dane odcinka, np: flask pokaz-odcinek Wyl101 D155"""
        from app.models import NetworkObject, Segment

        a = db.aliased(NetworkObject)
        b = db.aliased(NetworkObject)
        odc = db.session.scalar(
            select(Segment).join(a, Segment.obiekt_od_id == a.id)
            .join(b, Segment.obiekt_do_id == b.id)
            .where(a.kod == od, b.kod == do_)
        )
        if odc is None:
            click.echo(f"Nie znaleziono odcinka {od}-{do_}.")
            return
        click.echo(json.dumps(odc.to_dict(), ensure_ascii=False, indent=2))
        for kod in (od, do_):
            ob = db.session.scalar(select(NetworkObject).where(NetworkObject.kod == kod))
            click.echo(json.dumps(ob.to_dict(), ensure_ascii=False, indent=2))


def _podsumowanie() -> None:
    from app.models import (
        Connection,
        MaterialItem,
        NetworkObject,
        ObjectOccurrence,
        Profile,
        Segment,
        Sheet,
        SurveyPoint,
        TypObiektu,
    )

    click.echo("\n=== ZAWARTOSC BAZY ===")
    for etykieta, model in (
        ("arkusze", Sheet), ("profile", Profile), ("obiekty", NetworkObject),
        ("wystapienia", ObjectOccurrence), ("odcinki", Segment),
        ("polaczenia", Connection), ("punkty osnowy", SurveyPoint),
        ("pozycje materialowe", MaterialItem),
    ):
        n = db.session.scalar(select(func.count()).select_from(model))
        click.echo(f"  {etykieta:22} {n:6d}")

    click.echo("\n  obiekty wg typu:")
    wiersze = db.session.execute(
        select(NetworkObject.typ, func.count())
        .group_by(NetworkObject.typ).order_by(func.count().desc())
    ).all()
    for typ, n in wiersze:
        click.echo(f"    {typ.value if hasattr(typ, 'value') else typ:18} {n:6d}")

    dlugosc = db.session.scalar(select(func.sum(Segment.dlugosc_m)))
    click.echo(f"\n  laczna dlugosc odcinkow: {float(dlugosc or 0):.1f} m")


def _zapisz_do_env(klucz: str, wartosc: str, sciezka: str = ".env") -> None:
    """Dopisz albo podmien wpis w .env, nie ruszajac reszty pliku."""
    plik = Path(sciezka)
    linie = plik.read_text(encoding="utf-8").splitlines() if plik.exists() else []

    wynik, znaleziono = [], False
    for linia in linie:
        if linia.split("=", 1)[0].strip() == klucz:
            wynik.append(f"{klucz}={wartosc}")
            znaleziono = True
        else:
            wynik.append(linia)

    if not znaleziono:
        wynik.append(f"{klucz}={wartosc}")

    plik.write_text("\n".join(wynik) + "\n", encoding="utf-8")
