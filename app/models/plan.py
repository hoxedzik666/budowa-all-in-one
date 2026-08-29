"""Lokalizacje obiektow na planach sytuacyjnych.

Plany sytuacyjne maja wszystkie etykiety zamienione na krzywe wektorowe - w calym
18-stronicowym pliku jest tylko 667 unikalnych slow i ani jednego kodu obiektu.
Pozycje odzyskujemy OCR-em, dlatego kazdy rekord niesie **poziom pewnosci**
i flage recznej weryfikacji. Nic tu nie jest traktowane jak pewnik.

Wspolrzedne trzymamy w punktach PDF danej strony. To wystarcza do wyciecia mapki
i - po przeliczeniu przez skale rysunku - do odleglosci miedzy obiektami.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

# Skala rysunku 1:1000 -> 1 pt (1/72 cala) = 0.3528 mm na papierze = 0.3528 m w terenie.
MM_NA_PUNKT = 25.4 / 72.0


def punkty_na_metry(odleglosc_pt: float, mianownik_skali: int = 1000) -> float:
    """Zamien odleglosc na rysunku (pkt PDF) na metry w terenie."""
    return round(odleglosc_pt * MM_NA_PUNKT * mianownik_skali / 1000.0, 2)


class PlanSheet(db.Model):
    """Strona planu sytuacyjnego wraz z rozpoznana skala."""

    __tablename__ = "plan_sheet"

    id: Mapped[int] = mapped_column(primary_key=True)
    plik: Mapped[str] = mapped_column(String(255), index=True)
    nr_strony: Mapped[int] = mapped_column(Integer)

    szerokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    wysokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    skala: Mapped[int] = mapped_column(Integer, default=1000)

    # Ile etykiet OCR znalazl i ile z nich dalo sie dopasowac do bazy.
    etykiet_ocr: Mapped[int] = mapped_column(Integer, default=0)
    dopasowanych: Mapped[int] = mapped_column(Integer, default=0)
    uwagi: Mapped[str | None] = mapped_column(Text)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lokalizacje = relationship("PlanLocation", back_populates="strona",
                               cascade="all, delete-orphan")
    georef = relationship("PlanGeoref", back_populates="strona",
                          cascade="all, delete-orphan", uselist=False)
    kotwice = relationship("PlanAnchor", back_populates="strona",
                           cascade="all, delete-orphan",
                           order_by="PlanAnchor.id")

    def __repr__(self) -> str:
        return f"<PlanSheet s.{self.nr_strony} 1:{self.skala}>"


class PlanLocation(db.Model):
    """Gdzie na planie lezy dany obiekt - wynik OCR albo recznego wskazania."""

    __tablename__ = "plan_location"

    id: Mapped[int] = mapped_column(primary_key=True)
    obiekt_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )
    strona_id: Mapped[int] = mapped_column(
        ForeignKey("plan_sheet.id", ondelete="CASCADE"), index=True
    )

    x_pt: Mapped[float] = mapped_column(Numeric(10, 2))
    y_pt: Mapped[float] = mapped_column(Numeric(10, 2))

    # 0-100 wg tesseracta. Ponizej PROG_PEWNOSCI oznaczamy jako niepewne.
    pewnosc: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tekst_ocr: Mapped[str | None] = mapped_column(String(64))
    zrodlo: Mapped[str] = mapped_column(String(16), default="OCR")
    zweryfikowane: Mapped[bool] = mapped_column(Boolean, default=False)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    obiekt = relationship("NetworkObject")
    strona = relationship("PlanSheet", back_populates="lokalizacje")

    __table_args__ = (Index("ix_plan_location_obiekt_strona", "obiekt_id", "strona_id"),)

    def __repr__(self) -> str:
        return f"<PlanLocation {self.obiekt.kod if self.obiekt else '?'} s.{self.strona_id}>"

    @property
    def pewna(self) -> bool:
        return bool(self.zweryfikowane) or (self.pewnosc is not None and float(self.pewnosc) >= 70)

    def to_dict(self) -> dict:
        return {
            "obiekt": self.obiekt.kod if self.obiekt else None,
            "nr_strony": self.strona.nr_strony if self.strona else None,
            "x_pt": float(self.x_pt),
            "y_pt": float(self.y_pt),
            "pewnosc": float(self.pewnosc) if self.pewnosc is not None else None,
            "pewna": self.pewna,
            "tekst_ocr": self.tekst_ocr,
            "zrodlo": self.zrodlo,
            "zweryfikowane": self.zweryfikowane,
        }


class PlanGeoref(db.Model):
    """Zwiazanie arkusza planu z ukladem panstwowym PL-2000/5.

    Rysunek nie niesie zadnych wspolrzednych - nie ma warstw, metadanych ani
    siatki krzyzy. Dopiero wskazanie dwoch punktow o znanych wspolrzednych
    (kotwic) pozwala policzyc przeksztalcenie. Trzymamy je jako szesc liczb:

        Y (wschod) = ey_x * x_pt + ey_y * y_pt + ey_0
        X (polnoc) = nx_x * x_pt + nx_y * y_pt + nx_0

    Razem z nim zapisujemy **jakosc dopasowania** - skale, obrot i odchylke.
    Bez tego nie dalo by sie odroznic arkusza zwiazanego porzadnie od takiego,
    gdzie ktos wskazal nie ten reper.
    """

    __tablename__ = "plan_georef"

    id: Mapped[int] = mapped_column(primary_key=True)
    strona_id: Mapped[int] = mapped_column(
        ForeignKey("plan_sheet.id", ondelete="CASCADE"), unique=True, index=True
    )

    ey_x: Mapped[float] = mapped_column(Numeric(18, 10))
    ey_y: Mapped[float] = mapped_column(Numeric(18, 10))
    ey_0: Mapped[float] = mapped_column(Numeric(18, 4))
    nx_x: Mapped[float] = mapped_column(Numeric(18, 10))
    nx_y: Mapped[float] = mapped_column(Numeric(18, 10))
    nx_0: Mapped[float] = mapped_column(Numeric(18, 4))

    # Jakosc dopasowania - zawsze pokazywana obok wyniku.
    skala_m_na_pt: Mapped[float | None] = mapped_column(Numeric(12, 8))
    obrot_stopnie: Mapped[float | None] = mapped_column(Numeric(8, 4))
    rmse_m: Mapped[float | None] = mapped_column(Numeric(10, 3))
    liczba_kotwic: Mapped[int] = mapped_column(Integer, default=0)

    uklad: Mapped[str] = mapped_column(String(32), default="PL-2000/5")
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    strona = relationship("PlanSheet", back_populates="georef")

    @property
    def wspolczynniki(self) -> list[float]:
        return [float(self.ey_x), float(self.ey_y), float(self.ey_0),
                float(self.nx_x), float(self.nx_y), float(self.nx_0)]

    def przeksztalcenie(self):
        from app.services.georef import z_wspolczynnikow

        return z_wspolczynnikow(
            self.wspolczynniki,
            skala=float(self.skala_m_na_pt or 0),
            obrot=float(self.obrot_stopnie or 0),
            rmse=float(self.rmse_m or 0),
            kotwic=self.liczba_kotwic,
        )

    def to_dict(self) -> dict:
        return {
            "nr_strony": self.strona.nr_strony if self.strona else None,
            "uklad": self.uklad,
            **self.przeksztalcenie().to_dict(),
        }


class PlanAnchor(db.Model):
    """Punkt o znanych wspolrzednych wskazany na arkuszu.

    Zwykle jest to reper z osnowy (`punkt_id`), ale rownie dobrze moze byc
    dowolny punkt, ktorego wspolrzedne zna geodeta - stad mozliwosc wpisania
    X i Y wprost.
    """

    __tablename__ = "plan_anchor"

    id: Mapped[int] = mapped_column(primary_key=True)
    strona_id: Mapped[int] = mapped_column(
        ForeignKey("plan_sheet.id", ondelete="CASCADE"), index=True
    )
    punkt_id: Mapped[int | None] = mapped_column(
        ForeignKey("survey_point.id", ondelete="SET NULL")
    )

    x_pt: Mapped[float] = mapped_column(Numeric(10, 2))
    y_pt: Mapped[float] = mapped_column(Numeric(10, 2))
    x_gis: Mapped[float] = mapped_column(Numeric(12, 3))
    y_gis: Mapped[float] = mapped_column(Numeric(12, 3))
    nazwa: Mapped[str | None] = mapped_column(String(64))

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    strona = relationship("PlanSheet", back_populates="kotwice")
    punkt = relationship("SurveyPoint")

    __table_args__ = (
        Index("ix_plan_anchor_strona_nazwa", "strona_id", "nazwa", unique=True),
    )

    def kotwica(self):
        from app.services.georef import Kotwica

        return Kotwica(float(self.x_pt), float(self.y_pt),
                       float(self.x_gis), float(self.y_gis), self.nazwa or "")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nazwa": self.nazwa,
            "x_pt": float(self.x_pt),
            "y_pt": float(self.y_pt),
            "x_gis": float(self.x_gis),
            "y_gis": float(self.y_gis),
        }
