"""Rozpoznawanie, o czym mowi wpis uzytkownika.

Brygadzista pisze to, co ma na rysunku: `D155` albo `Wyl101-D155`. Nie zna
i nie powinien znac identyfikatorow z bazy. Ta sama zamiana potrzebna jest
w zadaniach, w dzienniku wykonawczym i w raportach dziennych - stad jedno
miejsce zamiast trzech kopii.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.extensions import db
from app.models import NetworkObject, Segment


def powiaz(fraza: str) -> tuple[NetworkObject | None, Segment | None, str | None]:
    """Zwraca (obiekt, odcinek, blad).

    Przy odcinku obiekt to jego poczatek - dzieki temu wpis zawsze wskazuje
    na cos konkretnego, nawet gdy odcinka nie ma w bazie.
    """
    fraza = (fraza or "").strip()
    if not fraza:
        return None, None, "Podaj obiekt (np. D155) albo odcinek (np. Wyl101-D155)."

    if "-" in fraza:
        od, _, do_ = fraza.partition("-")
        a, b = aliased(NetworkObject), aliased(NetworkObject)
        odcinek = db.session.scalar(
            select(Segment).join(a, Segment.obiekt_od_id == a.id)
            .join(b, Segment.obiekt_do_id == b.id)
            .where(func.lower(a.kod) == od.strip().lower(),
                   func.lower(b.kod) == do_.strip().lower())
        )
        if odcinek is not None:
            return odcinek.obiekt_od, odcinek, None

    obiekt = db.session.scalar(
        select(NetworkObject).where(func.lower(NetworkObject.kod) == fraza.lower())
    )
    if obiekt is not None:
        return obiekt, None, None
    return None, None, f"Nie znam obiektu ani odcinka „{fraza}”."
