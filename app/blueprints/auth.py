"""Logowanie i wylogowanie.

Aplikacja trzyma dane wykonawcze konkretnej budowy, wiec **caly interfejs jest
za logowaniem** - poza samym ekranem logowania, plikami statycznymi i endpointem
zdrowia (potrzebnym monitoringowi kontenera).
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)

# Endpointy dostepne bez zalogowania.
# Endpointy dostepne bez sesji. Lista jest krotka i kazda pozycja ma powod.
JAWNE = {
    "auth.zaloguj",        # inaczej nie dalo by sie zalogowac
    "static",              # style i skrypty ekranu logowania
    "api.zdrowie",         # monitoring kontenera dziala bez sesji
    "pwa.service_worker",  # przegladarka pobiera go przed zalogowaniem
    "pwa.offline",         # bez tego brak sieci konczy sie ekranem logowania,
                           # a nie informacja, ze nie ma zasiegu
}


def czy_wymaga_logowania(endpoint: str | None) -> bool:
    if endpoint is None:
        return False
    return endpoint not in JAWNE


@auth_bp.route("/login", methods=["GET", "POST"])
def zaloguj():
    if current_user.is_authenticated:
        return redirect(url_for("main.pulpit"))

    if request.method == "POST":
        login = (request.form.get("login") or "").strip()
        haslo = request.form.get("haslo") or ""
        pamietaj = bool(request.form.get("pamietaj"))

        uzytkownik = db.session.scalar(
            select(User).where(func.lower(User.login) == login.lower())
        )
        if uzytkownik is None or not uzytkownik.sprawdz_haslo(haslo):
            # Celowo nie mowimy, czy pomylil sie login, czy haslo.
            flash("Nieprawidłowy login albo hasło.", "danger")
            return render_template("pages/login.html", login=login), 401
        if not uzytkownik.aktywny:
            flash("To konto jest wyłączone. Skontaktuj się z administratorem.", "warning")
            return render_template("pages/login.html", login=login), 403

        login_user(uzytkownik, remember=pamietaj)
        uzytkownik.ostatnie_logowanie = datetime.now(timezone.utc)
        db.session.commit()

        dalej = request.args.get("next")
        # Otwarte przekierowanie to klasyczna dziura - przyjmujemy tylko sciezki wzgledne.
        if not dalej or not dalej.startswith("/") or dalej.startswith("//"):
            dalej = url_for("main.pulpit")
        return redirect(dalej)

    return render_template("pages/login.html", login="")


@auth_bp.get("/logout")
@login_required
def wyloguj():
    logout_user()
    flash("Wylogowano.", "success")
    return redirect(url_for("auth.zaloguj"))
