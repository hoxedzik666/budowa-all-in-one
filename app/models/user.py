"""Konta uzytkownikow.

Aplikacja trzyma dane wykonawcze konkretnej budowy, wiec caly interfejs jest
za logowaniem. Hasla nigdy nie leza w bazie jawnie - tylko skrot z werkzeuga.
"""
import enum
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Rola(str, enum.Enum):
    """Kto co moze.

    ADMIN       - zarzadza kontami, ma dostep do wszystkiego
    KIEROWNIK   - pelny podglad danych, przydziela zadania, ODBIERA odcinki
    BRYGADZISTA - podglad danych, wlasne zadania, raporty calej brygady
    MONTER      - czlowiek w wykopie: mierzy, zglasza gotowosc, pisze wlasny
                  raport. Nie przydziela zadan, nie odbiera robot i nie oglada
                  cudzych raportow.
    """

    ADMIN = "ADMIN"
    KIEROWNIK = "KIEROWNIK"
    BRYGADZISTA = "BRYGADZISTA"
    MONTER = "MONTER"


class User(UserMixin, db.Model):
    __tablename__ = "uzytkownik"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hash_hasla: Mapped[str] = mapped_column(String(255))

    imie_nazwisko: Mapped[str | None] = mapped_column(String(128))
    rola: Mapped[Rola] = mapped_column(Enum(Rola, name="rola"), default=Rola.BRYGADZISTA)
    aktywny: Mapped[bool] = mapped_column(Boolean, default=True)
    uwagi: Mapped[str | None] = mapped_column(Text)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ostatnie_logowanie: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    zadania_przypisane = relationship(
        "Task", foreign_keys="Task.przypisany_do_id", back_populates="przypisany_do"
    )
    zadania_utworzone = relationship(
        "Task", foreign_keys="Task.autor_id", back_populates="autor"
    )

    def __repr__(self) -> str:
        return f"<User {self.login} ({self.rola.value if self.rola else '?'})>"

    # --- hasla

    def ustaw_haslo(self, haslo: str) -> None:
        self.hash_hasla = generate_password_hash(haslo)

    def sprawdz_haslo(self, haslo: str) -> bool:
        return check_password_hash(self.hash_hasla, haslo)

    # --- Flask-Login

    @property
    def is_active(self) -> bool:  # noqa: D401 - nazwa wymagana przez Flask-Login
        """Dezaktywowane konto nie moze sie zalogowac."""
        return bool(self.aktywny)

    # --- uprawnienia
    #
    # Pytamy o mozliwosc, nie o role. Dzieki temu zmiana zakresu uprawnien to
    # poprawka w jednym miejscu, a nie polowanie na `rola ==` po widokach.

    @property
    def jest_adminem(self) -> bool:
        return self.rola == Rola.ADMIN

    @property
    def moze_przydzielac(self) -> bool:
        """Przydzielanie zadan innym osobom."""
        return self.rola in (Rola.ADMIN, Rola.KIEROWNIK)

    @property
    def moze_odbierac(self) -> bool:
        """Odbior odcinka i cofniecie odbioru.

        Zglosic wykonanie moze kazdy, kto stoi w wykopie - ale odbior jest
        decyzja kierownictwa. Stad dwa osobne stany: WYKONANY i ODEBRANY.
        """
        return self.rola in (Rola.ADMIN, Rola.KIEROWNIK)

    @property
    def widzi_cudze_raporty(self) -> bool:
        """Monter widzi wylacznie swoje wpisy, reszta - calej brygady."""
        return self.rola != Rola.MONTER

    @property
    def pracuje_w_wykopie(self) -> bool:
        """Role, dla ktorych domyslnym widokiem jest robota, nie zestawienia."""
        return self.rola in (Rola.BRYGADZISTA, Rola.MONTER)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "login": self.login,
            "imie_nazwisko": self.imie_nazwisko,
            "rola": self.rola.value if self.rola else None,
            "aktywny": self.aktywny,
            "utworzono": self.utworzono.isoformat() if self.utworzono else None,
            "ostatnie_logowanie": (
                self.ostatnie_logowanie.isoformat() if self.ostatnie_logowanie else None
            ),
        }
