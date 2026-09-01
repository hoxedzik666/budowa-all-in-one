"""Model sieci wod-kan: arkusze -> profile -> obiekty -> odcinki."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import Branza, StatusWykonania, TypObiektu, TypOdniesienia, ZrodloDanych
from app.models.typy import JSON_ELASTYCZNY


def _f(v):
    return float(v) if v is not None else None


class Sheet(db.Model):
    """Pojedynczy arkusz (strona) rysunku profili podluznych."""

    __tablename__ = "sheet"

    id: Mapped[int] = mapped_column(primary_key=True)
    plik: Mapped[str] = mapped_column(String(255), index=True)
    nr_strony: Mapped[int] = mapped_column(Integer)

    szerokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    wysokosc_pt: Mapped[float | None] = mapped_column(Numeric(10, 2))
    branza: Mapped[Branza] = mapped_column(Enum(Branza, name="branza"), default=Branza.NIEZNANA)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("Profile", back_populates="sheet", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("plik", "nr_strony", name="uq_sheet_plik_strona"),)

    def __repr__(self) -> str:
        return f"<Sheet {self.plik} s.{self.nr_strony}>"


class Profile(db.Model):
    """Profil podluzny - jeden ciag od punktu poczatkowego do koncowego.

    Oznaczenie profilu bierze sie z pola "OZNACZENIE PROFILU:" na rysunku,
    np. "Wyl101", "KT1". Profil nazywa sie zwykle od swojego pierwszego obiektu.
    """

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    oznaczenie: Mapped[str] = mapped_column(String(64), index=True)

    sheet_id: Mapped[int | None] = mapped_column(ForeignKey("sheet.id", ondelete="CASCADE"))
    branza: Mapped[Branza] = mapped_column(Enum(Branza, name="branza"), default=Branza.KD)
    typ_odniesienia: Mapped[TypOdniesienia] = mapped_column(
        Enum(TypOdniesienia, name="typ_odniesienia"), default=TypOdniesienia.DNO_KANALU
    )

    # "POZIOM POROWNAWCZY" - baza rysunku, nie dana projektowa. Trzymamy dla wiernosci.
    poziom_porownawczy: Mapped[float | None] = mapped_column(Numeric(8, 3))

    dlugosc_calkowita_m: Mapped[float | None] = mapped_column(Numeric(10, 2))
    blok_index: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[dict | None] = mapped_column(JSON_ELASTYCZNY)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sheet = relationship("Sheet", back_populates="profile")
    wystapienia = relationship(
        "ObjectOccurrence",
        back_populates="profil",
        cascade="all, delete-orphan",
        order_by="ObjectOccurrence.kolejnosc",
    )
    odcinki = relationship(
        "Segment",
        back_populates="profil",
        cascade="all, delete-orphan",
        order_by="Segment.kolejnosc",
    )

    __table_args__ = (
        UniqueConstraint("sheet_id", "oznaczenie", "blok_index", name="uq_profile_sheet_oznaczenie"),
    )

    def __repr__(self) -> str:
        return f"<Profile {self.oznaczenie}>"

    def to_dict(self, deep: bool = False) -> dict:
        out = {
            "id": self.id,
            "oznaczenie": self.oznaczenie,
            "branza": self.branza.value if self.branza else None,
            "typ_odniesienia": self.typ_odniesienia.value if self.typ_odniesienia else None,
            "poziom_porownawczy": _f(self.poziom_porownawczy),
            "dlugosc_calkowita_m": _f(self.dlugosc_calkowita_m),
            "nr_strony": self.sheet.nr_strony if self.sheet else None,
        }
        if deep:
            out["wystapienia"] = [w.to_dict() for w in self.wystapienia]
            out["odcinki"] = [o.to_dict() for o in self.odcinki]
        return out


class NetworkObject(db.Model):
    """OBIEKT - kanoniczny wezel sieci, unikalny po kodzie (np. D155, Wyl101, Wp65).

    Ten sam obiekt pojawia sie na wielu profilach (np. D155 jest koncem profilu
    Wyl101 i jednoczesnie ma wlasny profil). Dane projektowe trzymamy raz tutaj,
    a kontekst rysunkowy w ObjectOccurrence.
    """

    __tablename__ = "network_object"

    id: Mapped[int] = mapped_column(primary_key=True)
    kod: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    typ: Mapped[TypObiektu] = mapped_column(Enum(TypObiektu, name="typ_obiektu"), index=True)

    # --- geometria pionowa (serce danych wykonawczych) ---
    # Rzedna dna kanalu (grawitacja) albo osi przewodu (cisnienie) - patrz profil.
    rzedna_dna_kanalu: Mapped[float | None] = mapped_column(Numeric(8, 3))
    # "Rz.d.=" z opisu obiektu: rzedna dna STUDNI (osadnika/piaskownika),
    # zwykle 0.50 m ponizej dna kanalu, dla osadnika 1.50 m. To glebokosc kopania.
    rzedna_dna_studni: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_terenu_istn: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_terenu_proj: Mapped[float | None] = mapped_column(Numeric(8, 3))
    # zaglebienie = rzedna_terenu_proj - rzedna_dna_kanalu (moze byc ujemne dla wylotow)
    zaglebienie: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_dna_rowu: Mapped[float | None] = mapped_column(Numeric(8, 3))

    # --- wymiary ---
    dn_mm: Mapped[int | None] = mapped_column(Integer)
    srednica_studni_mm: Mapped[int | None] = mapped_column(Integer)

    material: Mapped[str | None] = mapped_column(String(64))
    opis: Mapped[str | None] = mapped_column(Text)
    uwagi: Mapped[str | None] = mapped_column(Text)

    # --- lokalizacja ---
    x: Mapped[float | None] = mapped_column(Numeric(12, 3))
    y: Mapped[float | None] = mapped_column(Numeric(12, 3))

    status: Mapped[StatusWykonania] = mapped_column(
        Enum(StatusWykonania, name="status_wykonania"), default=StatusWykonania.PROJEKT
    )
    zrodlo: Mapped[ZrodloDanych] = mapped_column(
        Enum(ZrodloDanych, name="zrodlo_danych"), default=ZrodloDanych.PDF_PROFIL
    )
    surowe: Mapped[dict | None] = mapped_column(JSON_ELASTYCZNY)

    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    zmieniono: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    wystapienia = relationship(
        "ObjectOccurrence", back_populates="obiekt", cascade="all, delete-orphan"
    )
    odcinki_wychodzace = relationship(
        "Segment", foreign_keys="Segment.obiekt_od_id", back_populates="obiekt_od"
    )
    odcinki_wchodzace = relationship(
        "Segment", foreign_keys="Segment.obiekt_do_id", back_populates="obiekt_do"
    )

    __table_args__ = (Index("ix_network_object_typ_kod", "typ", "kod"),)

    def __repr__(self) -> str:
        return f"<Obiekt {self.kod}>"

    @property
    def glebokosc_wykopu(self) -> float | None:
        """Od terenu projektowanego do dna studni - tyle trzeba wykopac."""
        if self.rzedna_terenu_proj is None:
            return None
        dol = self.rzedna_dna_studni if self.rzedna_dna_studni is not None else self.rzedna_dna_kanalu
        if dol is None:
            return None
        return round(float(self.rzedna_terenu_proj) - float(dol), 3)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kod": self.kod,
            "typ": self.typ.value if self.typ else None,
            "rzedna_dna_kanalu": _f(self.rzedna_dna_kanalu),
            "rzedna_dna_studni": _f(self.rzedna_dna_studni),
            "rzedna_terenu_istn": _f(self.rzedna_terenu_istn),
            "rzedna_terenu_proj": _f(self.rzedna_terenu_proj),
            "zaglebienie": _f(self.zaglebienie),
            "glebokosc_wykopu": self.glebokosc_wykopu,
            "dn_mm": self.dn_mm,
            "srednica_studni_mm": self.srednica_studni_mm,
            "material": self.material,
            "opis": self.opis,
            "status": self.status.value if self.status else None,
            "zrodlo": self.zrodlo.value if self.zrodlo else None,
        }


class ObjectOccurrence(db.Model):
    """Wystapienie obiektu na konkretnym profilu, z pikietazem."""

    __tablename__ = "object_occurrence"

    id: Mapped[int] = mapped_column(primary_key=True)
    profil_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"), index=True)
    obiekt_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )

    kolejnosc: Mapped[int] = mapped_column(Integer, default=0)
    hektometr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    odleglosc_czastkowa: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Rzedne odczytane na TYM profilu. Studnia ma tyle rzednych dna, ile
    # podlaczonych rur - kanoniczna (w network_object) jest najnizsza z nich.
    rzedna_dna: Mapped[float | None] = mapped_column(Numeric(8, 3))
    zaglebienie: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_terenu_proj: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_terenu_istn: Mapped[float | None] = mapped_column(Numeric(8, 3))
    opis: Mapped[str | None] = mapped_column(Text)
    bbox: Mapped[dict | None] = mapped_column(JSON_ELASTYCZNY)

    profil = relationship("Profile", back_populates="wystapienia")
    obiekt = relationship("NetworkObject", back_populates="wystapienia")

    __table_args__ = (UniqueConstraint("profil_id", "obiekt_id", "kolejnosc", name="uq_occurrence"),)

    def to_dict(self) -> dict:
        return {
            "kolejnosc": self.kolejnosc,
            "hektometr": _f(self.hektometr),
            "odleglosc_czastkowa": _f(self.odleglosc_czastkowa),
            "rzedna_dna": _f(self.rzedna_dna),
            "zaglebienie": _f(self.zaglebienie),
            "rzedna_terenu_proj": _f(self.rzedna_terenu_proj),
            "rzedna_terenu_istn": _f(self.rzedna_terenu_istn),
            "opis": self.opis,
            "obiekt": self.obiekt.to_dict() if self.obiekt else None,
        }


class Segment(db.Model):
    """ODCINEK - rura miedzy dwoma obiektami, np. Wyl101 -> D155.

    To podstawowa jednostka robocza brygady: jedna srednica, jeden spadek,
    jedna dlugosc, jeden material.
    """

    __tablename__ = "segment"

    id: Mapped[int] = mapped_column(primary_key=True)
    profil_id: Mapped[int] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"), index=True)
    obiekt_od_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )
    obiekt_do_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )

    kolejnosc: Mapped[int] = mapped_column(Integer, default=0)
    dlugosc_m: Mapped[float | None] = mapped_column(Numeric(10, 2))
    dn_mm: Mapped[int | None] = mapped_column(Integer)
    material: Mapped[str | None] = mapped_column(String(64))

    # Spadek trzymamy w promilach - jednostka projektowa; procenty licza sie z tego.
    spadek_promile: Mapped[float | None] = mapped_column(Numeric(8, 3))

    rzedna_dna_od: Mapped[float | None] = mapped_column(Numeric(8, 3))
    rzedna_dna_do: Mapped[float | None] = mapped_column(Numeric(8, 3))

    status: Mapped[StatusWykonania] = mapped_column(
        Enum(StatusWykonania, name="status_wykonania"), default=StatusWykonania.PROJEKT
    )

    # Odcinek, ktorego danych nie da sie pogodzic (dlugosc 0 m, spadek 31%...).
    # Nie zgadujemy poprawnej wartosci - oznaczamy i podajemy powod.
    podejrzany: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    powod_podejrzenia: Mapped[str | None] = mapped_column(Text)

    surowe: Mapped[dict | None] = mapped_column(JSON_ELASTYCZNY)
    utworzono: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profil = relationship("Profile", back_populates="odcinki")
    obiekt_od = relationship(
        "NetworkObject", foreign_keys=[obiekt_od_id], back_populates="odcinki_wychodzace"
    )
    obiekt_do = relationship(
        "NetworkObject", foreign_keys=[obiekt_do_id], back_populates="odcinki_wchodzace"
    )

    __table_args__ = (
        UniqueConstraint("profil_id", "obiekt_od_id", "obiekt_do_id", name="uq_segment"),
        CheckConstraint("obiekt_od_id <> obiekt_do_id", name="ck_segment_rozne_konce"),
    )

    def __repr__(self) -> str:
        return f"<Odcinek {self.nazwa} L={self.dlugosc_m} DN{self.dn_mm}>"

    @property
    def nazwa(self) -> str:
        a = self.obiekt_od.kod if self.obiekt_od else "?"
        b = self.obiekt_do.kod if self.obiekt_do else "?"
        return f"{a}-{b}"

    @property
    def spadek_procent(self) -> float | None:
        if self.spadek_promile is None:
            return None
        return round(float(self.spadek_promile) / 10.0, 4)

    @property
    def kierunek_rysunku(self) -> str | None:
        """Czy profil narysowano zgodnie ze splywem, czy pod prad.

        Profile podluzne rysuje sie od wylotu w gore sieci, wiec na 633 z 647
        odcinkow `rzedna_dna_od` jest NIZSZA niz `rzedna_dna_do`. To nie blad
        danych, tylko konwencja rysunku - ale bez tej informacji spadek
        wyliczony z rzednych wychodzil ujemny i taki szedl do API.
        """
        if self.surowe and self.surowe.get("kierunek_rysunku"):
            return self.surowe["kierunek_rysunku"]
        if self.rzedna_dna_od is None or self.rzedna_dna_do is None:
            return None
        return "z_pradem" if float(self.rzedna_dna_od) >= float(self.rzedna_dna_do) else "pod_prad"

    @property
    def spadek_wyliczony_promile(self) -> float | None:
        """Spadek policzony z rzednych - do kontroli tego z rysunku.

        Zawsze dodatni: spadek to wielkosc bez znaku, a o zwrocie mowi
        `kierunek_rysunku`.
        """
        if self.rzedna_dna_od is None or self.rzedna_dna_do is None or not self.dlugosc_m:
            return None
        roznica = abs(float(self.rzedna_dna_od) - float(self.rzedna_dna_do))
        return round(roznica / float(self.dlugosc_m) * 1000.0, 3)

    @property
    def rozjazd_spadku_promile(self) -> float | None:
        """O ile spadek z rysunku rozni sie od policzonego z rzednych."""
        wyliczony = self.spadek_wyliczony_promile
        if wyliczony is None or self.spadek_promile is None:
            return None
        return round(abs(abs(float(self.spadek_promile)) - wyliczony), 3)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nazwa": self.nazwa,
            "profil_id": self.profil_id,
            "od": self.obiekt_od.kod if self.obiekt_od else None,
            "do": self.obiekt_do.kod if self.obiekt_do else None,
            "kolejnosc": self.kolejnosc,
            "dlugosc_m": _f(self.dlugosc_m),
            "dn_mm": self.dn_mm,
            "material": self.material,
            "spadek_promile": _f(self.spadek_promile),
            "spadek_procent": self.spadek_procent,
            "spadek_wyliczony_promile": self.spadek_wyliczony_promile,
            "rozjazd_spadku_promile": self.rozjazd_spadku_promile,
            "kierunek_rysunku": self.kierunek_rysunku,
            "rzedna_dna_od": _f(self.rzedna_dna_od),
            "rzedna_dna_do": _f(self.rzedna_dna_do),
            "status": self.status.value if self.status else None,
            "podejrzany": bool(self.podejrzany),
            "powod_podejrzenia": self.powod_podejrzenia,
        }


class Connection(db.Model):
    """Przylacze / wlaczenie do obiektu.

    Zrodlo: opisy typu "Proj. wlaczenie kanalu Wp133 O400, Rz.d.=43.46",
    katy 115 st. (K1) z rysunku oraz kolumna "Odbiornik" z arkusza Wpusty.
    """

    __tablename__ = "connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    obiekt_id: Mapped[int] = mapped_column(
        ForeignKey("network_object.id", ondelete="CASCADE"), index=True
    )
    obiekt_zrodlowy_kod: Mapped[str | None] = mapped_column(String(64), index=True)

    dn_mm: Mapped[int | None] = mapped_column(Integer)
    rzedna: Mapped[float | None] = mapped_column(Numeric(8, 3))
    kat_stopnie: Mapped[float | None] = mapped_column(Numeric(6, 2))
    oznaczenie_kanalu: Mapped[str | None] = mapped_column(String(16))
    kierunek: Mapped[str] = mapped_column(String(16), default="DOPLYW")
    opis: Mapped[str | None] = mapped_column(Text)
    zrodlo: Mapped[ZrodloDanych] = mapped_column(
        Enum(ZrodloDanych, name="zrodlo_danych"), default=ZrodloDanych.PDF_PROFIL
    )

    obiekt = relationship("NetworkObject")

    # Uwaga: import materialowy uruchamiany kilka razy potrafil zdublowac komplet
    # polaczen (2442 wiersze zamiast 771). Przyczyne usuwa kasowanie po zrodle
    # w importerach, a pilnuje tego indeks `uq_connection_naturalny` zakladany
    # przez `app/services/schemat.py` - tam, bo najpierw trzeba odsiac duplikaty
    # z istniejacej bazy, inaczej zalozenie indeksu by sie wywalilo.

    def to_dict(self) -> dict:
        return {
            "obiekt_zrodlowy": self.obiekt_zrodlowy_kod,
            "dn_mm": self.dn_mm,
            "rzedna": _f(self.rzedna),
            "kat_stopnie": _f(self.kat_stopnie),
            "oznaczenie_kanalu": self.oznaczenie_kanalu,
            "kierunek": self.kierunek,
            "opis": self.opis,
        }
