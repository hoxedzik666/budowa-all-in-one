"""Panel administracyjny - zarzadzanie kontami."""
from __future__ import annotations

import secrets
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.models import Rola, Task, User

panel_bp = Blueprint("panel", __name__)

DLUGOSC_HASLA = 14


def tylko_admin(widok):
    @wraps(widok)
    def opakowany(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.jest_adminem:
            abort(403, "Ta część panelu jest dostępna tylko dla administratora.")
        return widok(*args, **kwargs)
    return opakowany


def wygeneruj_haslo() -> str:
    return secrets.token_urlsafe(DLUGOSC_HASLA)


@panel_bp.get("/panel/uzytkownicy")
@login_required
@tylko_admin
def uzytkownicy():
    konta = list(db.session.scalars(select(User).order_by(User.login)))
    zadan = dict(db.session.execute(
        select(Task.przypisany_do_id, func.count()).group_by(Task.przypisany_do_id)
    ).all())
    return render_template("pages/panel.html", konta=konta, role=list(Rola),
                           zadan=zadan, nowe_haslo=request.args.get("haslo"),
                           nowy_login=request.args.get("login"))


@panel_bp.post("/panel/uzytkownicy/dodaj")
@login_required
@tylko_admin
def dodaj_uzytkownika():
    login = (request.form.get("login") or "").strip()
    if not login:
        flash("Login jest wymagany.", "warning")
        return redirect(url_for("panel.uzytkownicy"))

    istnieje = db.session.scalar(select(User).where(func.lower(User.login) == login.lower()))
    if istnieje is not None:
        flash(f"Konto „{login}” już istnieje.", "warning")
        return redirect(url_for("panel.uzytkownicy"))

    rola = request.form.get("rola") or Rola.BRYGADZISTA.value
    haslo = (request.form.get("haslo") or "").strip() or wygeneruj_haslo()

    uzytkownik = User(
        login=login,
        imie_nazwisko=(request.form.get("imie_nazwisko") or "").strip() or None,
        rola=Rola[rola] if rola in Rola.__members__ else Rola.BRYGADZISTA,
    )
    uzytkownik.ustaw_haslo(haslo)
    db.session.add(uzytkownik)
    db.session.commit()

    flash(f"Utworzono konto „{login}”. Hasło pokazujemy tylko raz — zapisz je teraz.", "success")
    return redirect(url_for("panel.uzytkownicy", haslo=haslo, login=login))


@panel_bp.post("/panel/uzytkownicy/<int:uid>/haslo")
@login_required
@tylko_admin
def reset_hasla(uid: int):
    uzytkownik = db.session.get(User, uid)
    if uzytkownik is None:
        abort(404)
    haslo = wygeneruj_haslo()
    uzytkownik.ustaw_haslo(haslo)
    db.session.commit()
    flash(f"Nowe hasło dla „{uzytkownik.login}”. Pokazujemy je tylko raz.", "success")
    return redirect(url_for("panel.uzytkownicy", haslo=haslo, login=uzytkownik.login))


@panel_bp.post("/panel/uzytkownicy/<int:uid>/przelacz")
@login_required
@tylko_admin
def przelacz_aktywnosc(uid: int):
    uzytkownik = db.session.get(User, uid)
    if uzytkownik is None:
        abort(404)
    if uzytkownik.id == current_user.id:
        flash("Nie można wyłączyć własnego konta — stracisz dostęp do panelu.", "warning")
        return redirect(url_for("panel.uzytkownicy"))

    if uzytkownik.jest_adminem and uzytkownik.aktywny:
        aktywni_admini = db.session.scalar(
            select(func.count()).select_from(User)
            .where(User.rola == Rola.ADMIN, User.aktywny.is_(True))
        )
        if aktywni_admini <= 1:
            flash("To jedyny aktywny administrator — nie można go wyłączyć.", "warning")
            return redirect(url_for("panel.uzytkownicy"))

    uzytkownik.aktywny = not uzytkownik.aktywny
    db.session.commit()
    flash(
        f"Konto „{uzytkownik.login}” zostało "
        f"{'włączone' if uzytkownik.aktywny else 'wyłączone'}.",
        "success",
    )
    return redirect(url_for("panel.uzytkownicy"))


@panel_bp.post("/panel/uzytkownicy/<int:uid>/rola")
@login_required
@tylko_admin
def zmien_role(uid: int):
    uzytkownik = db.session.get(User, uid)
    if uzytkownik is None:
        abort(404)
    rola = request.form.get("rola")
    if rola not in Rola.__members__:
        flash("Nieznana rola.", "warning")
        return redirect(url_for("panel.uzytkownicy"))
    uzytkownik.rola = Rola[rola]
    db.session.commit()
    flash(f"„{uzytkownik.login}” ma teraz rolę {rola}.", "success")
    return redirect(url_for("panel.uzytkownicy"))
