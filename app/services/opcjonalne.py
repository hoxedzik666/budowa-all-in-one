"""Biblioteki, ktorych na telefonie po prostu nie ma.

Skad problem
------------
Termux to Android, czyli bionic libc. Kola z PyPI budowane dla Linuksa tam nie
wchodza, a PyMuPDF ze zrodel oznacza zbudowanie calego MuPDF - na telefonie to
nie jest realne. Ta sama historia dotyczy `pyproj` (potrzebuje PROJ)
i `pytesseract` (potrzebuje binarki tesseract).

Do tej pory `import fitz` stal na poziomie modulu w `app/blueprints/mapa.py`,
wiec brak PyMuPDF przewracal **cala aplikacje**, a nie jedna funkcje: nie dalo
sie otworzyc ani karty odcinka, ani niwelatora, ani listy zadan. Tymczasem
dziewiec dziesiatych narzedzia nie ma z PDF-em nic wspolnego.

Rozwiazanie
-----------
`LeniwyModul` udaje modul: import odklada do pierwszego uzycia, a gdy modulu
nie ma - zglasza `BrakModulu`, ktory Flask zamienia na czytelna strone z kodem
503. Podmiana w kodzie jest jednolinijkowa (`import fitz` ->
`from app.services.opcjonalne import fitz`), wiec kilkadziesiat wywolan
`fitz.Rect(...)` zostaje nietknietych.

Wazne: adnotacje typu (`clip: fitz.Rect | None`) sa napisami dzieki
`from __future__ import annotations` w kazdym z tych modulow - nikt ich nie
wykonuje przy imporcie. Gdyby ktos napisal `def f(x=fitz.Rect())`, wartosc
domyslna policzylaby sie od razu i zglosilaby `BrakModulu` juz przy starcie;
takich miejsc w projekcie nie ma i nie powinno byc.
"""
from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType


class BrakModulu(RuntimeError):
    """Funkcja wymaga biblioteki, ktorej w tej instalacji nie ma.

    To nie jest blad programu - to informacja, ze o tej funkcji trzeba poprosic
    komputer. Dlatego niesie trzy rzeczy: nazwe biblioteki, po co ona jest
    i co z tym zrobic.
    """

    def __init__(self, nazwa: str, po_co: str, jak_naprawic: str) -> None:
        self.nazwa = nazwa
        self.po_co = po_co
        self.jak_naprawic = jak_naprawic
        super().__init__(f"Brak biblioteki {nazwa}: {po_co}. {jak_naprawic}")


# Po co kazda z nich jest i co zrobic, gdy jej nie ma. Teksty ida wprost
# na ekran - pisane sa do brygadzisty, nie do programisty.
OPIS: dict[str, tuple[str, str]] = {
    "fitz": (
        "odczyt i rysowanie plików PDF — mapa planów, kafelki, wycinki profili "
        "i import dokumentacji",
        "Na telefonie tej biblioteki nie da się zainstalować. Te rzeczy robi się "
        "na komputerze; telefon dostaje gotową bazę (komenda `flask zrzut-sqlite`).",
    ),
    "pyproj": (
        "przeliczenie pozycji z GPS na układ PL-2000/5",
        "Na komputerze jest w `requirements.txt`. W Termuxie: `pkg install proj`, "
        "potem `pip install pyproj`.",
    ),
    "pytesseract": (
        "odczyt napisów z rysunku (droga historyczna, docs/project-docs/04)",
        "Wymaga programu tesseract: `pkg install tesseract` albo obrazu Dockera.",
    ),
    "pdfplumber": (
        "pomocniczy odczyt tabel z PDF",
        "Instaluje się razem z resztą `requirements.txt` na komputerze.",
    ),
    "PIL": (
        "obróbka zdjęć z budowy i rysowanie kodów QR",
        "W Termuxie: `pkg install python-pillow`.",
    ),
}


def _blad(nazwa: str) -> BrakModulu:
    # "PIL.Image" ma szukac opisu pod "PIL" - opis dotyczy calej biblioteki,
    # a nie pojedynczego modulu w srodku.
    opis = OPIS.get(nazwa) or OPIS.get(nazwa.split(".")[0])
    po_co, jak = opis or ("działanie tej funkcji", f"Zainstaluj `{nazwa}`.")
    return BrakModulu(nazwa, po_co, jak)


class LeniwyModul:
    """Modul importowany dopiero przy pierwszym uzyciu.

    Sam import (`from app.services.opcjonalne import fitz`) nic nie kosztuje
    i nigdy nie zawodzi. Dopiero siegniecie po `fitz.cokolwiek` sprowadza
    prawdziwy modul albo zglasza `BrakModulu`.
    """

    def __init__(self, nazwa: str) -> None:
        self._nazwa = nazwa
        self._modul: ModuleType | None = None

    def zaladuj(self) -> ModuleType:
        if self._modul is None:
            try:
                self._modul = importlib.import_module(self._nazwa)
            except ImportError as exc:
                raise _blad(self._nazwa) from exc
        return self._modul

    def __getattr__(self, atrybut: str):
        # Nazwy z podkreslnikiem sa nasze wlasne - nie ma po co dla nich
        # importowac calej biblioteki (a `copy`/`pickle` pytaja o `__deepcopy__`
        # i podobne, wiec bez tego warunku import wywolywalby sie znienacka).
        if atrybut.startswith("_"):
            raise AttributeError(atrybut)
        return getattr(self.zaladuj(), atrybut)

    def __repr__(self) -> str:
        stan = "zaladowany" if self._modul is not None else "nieuzywany"
        return f"<LeniwyModul {self._nazwa} ({stan})>"


fitz = LeniwyModul("fitz")
pyproj = LeniwyModul("pyproj")
pytesseract = LeniwyModul("pytesseract")


def wymagaj(nazwa: str) -> ModuleType:
    """Zwroc modul albo zglos `BrakModulu` z gotowym komunikatem.

    Do uzycia tam, gdzie import i tak jest wewnatrz funkcji - wtedy `LeniwyModul`
    nic by nie wniosl, a komunikat ma byc ten sam.
    """
    try:
        return importlib.import_module(nazwa)
    except ImportError as exc:
        raise _blad(nazwa) from exc


def czy_jest(nazwa: str) -> bool:
    """Czy modul da sie zaimportowac - bez importowania go.

    `find_spec` tylko szuka pliku, wiec nadaje sie do diagnostyki (`/api/zdrowie`),
    gdzie zaladowanie PyMuPDF kosztowaloby wiecej niz cala odpowiedz.
    """
    try:
        return importlib.util.find_spec(nazwa) is not None
    except (ImportError, ValueError):
        return False


def dostepne() -> dict[str, bool]:
    """Stan bibliotek opcjonalnych - do `/api/zdrowie` i do diagnostyki."""
    return {nazwa: czy_jest(nazwa) for nazwa in sorted(OPIS)}
