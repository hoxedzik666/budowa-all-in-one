"""Slowniki typow uzywane w modelu sieci wod-kan."""
import enum


class TypObiektu(str, enum.Enum):
    """Rodzaj wezla w sieci. Skroty zgodne z oznaczeniami projektanta."""

    WYLOT = "WYLOT"                    # Wyl - wylot do rowu / zbiornika
    STUDNIA = "STUDNIA"                # D   - studnia rewizyjna / z piaskownikiem
    WPUST = "WPUST"                    # Wp  - wpust deszczowy (uliczny)
    SEPARATOR = "SEPARATOR"            # SEP - separator substancji ropopochodnych
    OSADNIK = "OSADNIK"                # O   - osadnik
    TROJNIK = "TROJNIK"                # Tr  - trojnik
    LUK = "LUK"                        # luk / zalamanie trasy
    WEZEL_KT = "WEZEL_KT"              # wezel na kanale tlocznym
    SCIEK_SKARPOWY = "SCIEK_SKARPOWY"  # sciek skarpowy
    INNY = "INNY"


class Branza(str, enum.Enum):
    """Rodzaj sieci - decyduje o interpretacji rzednych i walidacji."""

    KD = "KD"                          # kanalizacja deszczowa (grawitacyjna)
    KT = "KT"                          # kanal tloczny (cisnieniowy)
    SCIEK_SKARPOWY = "SCIEK_SKARPOWY"  # odwodnienie powierzchniowe skarp
    NIEZNANA = "NIEZNANA"


class TypOdniesienia(str, enum.Enum):
    """Do czego odnosza sie rzedne profilu."""

    DNO_KANALU = "DNO_KANALU"    # grawitacja: rzedna dna rury (Rz.d.)
    OS_PRZEWODU = "OS_PRZEWODU"  # cisnienie: rzedna osi rury (Rz.o.)


class ZrodloDanych(str, enum.Enum):
    PDF_PROFIL = "PDF_PROFIL"
    XLSX_MATERIAL = "XLSX_MATERIAL"
    TXT_OSNOWA = "TXT_OSNOWA"
    RECZNE = "RECZNE"


class StatusWykonania(str, enum.Enum):
    """Postep robot - do sledzenia przez kierownika budowy."""

    PROJEKT = "PROJEKT"
    WYTYCZONY = "WYTYCZONY"
    W_TRAKCIE = "W_TRAKCIE"
    WYKONANY = "WYKONANY"
    ODEBRANY = "ODEBRANY"


# Mapa prefiksu kodu obiektu -> typ. Kolejnosc ma znaczenie: dluzsze prefiksy
# musza byc sprawdzane pierwsze, inaczej "Wyl101" zostanie zlapane przez "W".
PREFIX_TYP = [
    ("Wyl", TypObiektu.WYLOT),
    ("SEP", TypObiektu.SEPARATOR),
    ("Wp", TypObiektu.WPUST),
    ("Tr", TypObiektu.TROJNIK),
    ("KT", TypObiektu.WEZEL_KT),
    ("D", TypObiektu.STUDNIA),
    ("O", TypObiektu.OSADNIK),
]
