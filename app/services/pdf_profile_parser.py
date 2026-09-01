"""Parser profili podluznych z pliku "Profile Scalone.pdf".

Rozpoznana struktura arkusza (zweryfikowana na wszystkich 13 stronach)
--------------------------------------------------------------------
Arkusz to poziomy pas ok. 5669 x 1190 pt. W jego dolnej czesci jest tabela
danych, powyzej rysunek profilu (linie terenu i kanalu).

Lewa kolumna arkusza (x < ~300) zawiera legende pasm - po jednym komplecie
na strone:

    OZNACZENIE PROFILU:        <- nazwa profilu
    POZIOM PORÓWNAWCZY         <- baza rysunku, np. "70.00m n.p.m."
    RZĘDNA TERENU PROJ.
    RZĘDNA TERENU ISTN.
    RZĘDNA DNA KANAŁU          (albo RZĘDNA OSI PRZEWODU dla kanalu tlocznego)
    ZAGŁĘBIENIE DNA KANAŁU     (albo ZAGŁĘBIENIE OSI PRZEWODU)
    SPADKI, DŁUGOŚCI
    ŚREDNICA, MATERIAŁ
    ODLEGŁOŚCI                 <- pionowo: pikietaz narastajaco, poziomo: odl. czastkowa
    HEKTOMETRY                 <- oznaczenia punktow trasy (kody obiektow)

Na jednym arkuszu lezy obok siebie wiele blokow (profili). Kazdy blok ma przy
swojej lewej krawedzi wlasny naglowek: nazwa + poziom porownawczy + "n.p.m.".

Wartosci liczbowe w kolumnach wezlow sa OBROCONE O 90 stopni (dir = (0,-1)),
opisy obiektow tez. Wartosci odcinkow (spadek, srednica, dlugosc) sa poziome
i leza miedzy kolumnami sasiednich wezlow.

Przyklad - profil "D155" ze strony 6:

    HEKTOMETRY   Wyl101 (x=2734.8)            D155 (x=2852.9)
    ODLEGL.      0.00                20.5     20.31
    SREDNICA               Ø500
    SPADKI                 0.3%      20.5m
    ZAGLEBIENIE  0.00                         1.05
    RZ. DNA      82.70                        82.76
    TEREN ISTN.  83.57                        83.64
    TEREN PROJ.  82.70                        83.81
    OPIS         Wylot                        Studnia z piaskownikiem
                                              DN1500, Rz.d.=82.26

czyli: odcinek Wyl101-D155, dlugosc 20.5 m, Ø500, spadek 0.3%.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# PyMuPDF pod udawana nazwa - import odklada sie do pierwszego uzycia,
# zeby brak biblioteki (telefon) nie przewracal calej aplikacji.
# Szczegoly: app/services/opcjonalne.py
from app.services.opcjonalne import fitz

# ---------------------------------------------------------------- stale

# Nagłówki pasm -> klucz kanoniczny. Kolejnosc wazna: dluzsze wzorce pierwsze.
NAGLOWKI = [
    ("OZNACZENIE PROFILU", "OZNACZENIE"),
    ("POZIOM PORÓWNAWCZY", "POZIOM"),
    ("RZĘDNA TERENU PROJ", "TEREN_PROJ"),
    ("RZĘDNA TERENU ISTN", "TEREN_ISTN"),
    ("RZĘDNA DNA KANAŁU", "DNO"),
    ("RZĘDNA OSI PRZEWODU", "DNO"),
    ("ZAGŁĘBIENIE DNA KANAŁU", "ZAGLEBIENIE"),
    ("ZAGŁĘBIENIE OSI PRZEWODU", "ZAGLEBIENIE"),
    ("SPADKI, DŁUGOŚCI", "SPADKI"),
    ("ŚREDNICA, MATERIAŁ", "SREDNICA"),
    ("ODLEGŁOŚCI", "ODLEGLOSCI"),
    ("HEKTOMETRY", "HEKTOMETRY"),
]

KOLEJNOSC_PASM = [
    "OZNACZENIE", "POZIOM", "TEREN_PROJ", "TEREN_ISTN", "DNO",
    "ZAGLEBIENIE", "SPADKI", "SREDNICA", "ODLEGLOSCI", "HEKTOMETRY",
]

# Kod obiektu. "S.S.S." i podobne smieci z nakladajacych sie napisow obcinamy.
RE_KOD = re.compile(r"^(?:S\.S\.S\.)?(Wyl|SEP|Ws|Wo|Wp|Tr|KT|Ł|L|D|O)\s?(\d+(?:[.,]\d+)?[a-z]?)$")
RE_KOD_ALIAS = re.compile(r"^(.+?)\s*=\s*(.+)$")

RE_LICZBA = re.compile(r"^-?\d+[.,]\d+$|^-?\d+$")
RE_POZIOM = re.compile(r"^(\d+[.,]\d+)\s*m(?:\s*n\.?p\.?m\.?)?$", re.I)
RE_SREDNICA = re.compile(r"Ø\s*(\d{2,4})")
RE_DLUGOSC = re.compile(r"L\s*=\s*(\d+[.,]?\d*)\s*m", re.I)
RE_DLUGOSC_SAMA = re.compile(r"^(\d+[.,]?\d*)\s*m$", re.I)
RE_SPADEK = re.compile(r"^(-?\d+[.,]?\d*)\s*%$")
RE_RZ_STUDNI = re.compile(r"Rz\.\s*[dof]\.?\s*=\s*(\d+[.,]\d+)", re.I)
RE_DN_STUDNI = re.compile(r"DN\s*(\d{3,4})", re.I)
RE_KAT = re.compile(r"(\d+(?:[.,]\d+)?)\s*°(?:\s*\((K\d)\))?")
RE_WLACZENIE = re.compile(
    r"(?:Proj\.\s*)?w[łl][ąa]czenie.*?((?:Wyl|Wp|D|SEP|O|Tr|KT)\s?\d+[a-z]?)?.*?Ø\s*(\d{2,4}).*?Rz\.\s*[do]\.?\s*=\s*(\d+[.,]\d+)",
    re.I,
)

TOL_X_WEZEL = 18.0  # pt - dopasowanie wartosci do kolumny wezla

# Opis obiektu vs adnotacja rysunkowa. "Rz.d.=" wystepuje w obu, ale znaczy
# co innego: w opisie to dno studni, w adnotacji rzedna wlotu przylacza.
OPIS_OBIEKTU = ("studnia", "studzienka", "wpust", "wylot", "osadnik", "separator",
                "trójnik", "trojnik", "łuk", "luk", "komora", "zbiornik", "kaskada",
                "wylot ", "piaskownik")
ADNOTACJA = ("proj. włączenie", "proj. wlaczenie", "włączenie", "wlaczenie",
             "skrzyżowanie", "skrzyzowanie", "istn.", "kolizja")


def _num(txt: str) -> float | None:
    try:
        return float(txt.replace(",", ".").replace(" ", ""))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- struktury


@dataclass
class Span:
    t: str
    x0: float
    y0: float
    x1: float
    y1: float
    pion: bool

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class WezelPDF:
    kod: str
    alias: str | None = None
    x: float = 0.0
    hektometr: float | None = None
    zaglebienie: float | None = None
    rzedna_dna: float | None = None
    rzedna_terenu_istn: float | None = None
    rzedna_terenu_proj: float | None = None
    rzedna_dna_studni: float | None = None
    srednica_studni_mm: int | None = None
    opis: str | None = None
    dodatkowe_wloty: list[float] = field(default_factory=list)
    adnotacje: list[str] = field(default_factory=list)
    bbox: dict | None = None

    def to_dict(self) -> dict:
        return {
            "kod": self.kod, "alias": self.alias, "hektometr": self.hektometr,
            "zaglebienie": self.zaglebienie, "rzedna_dna": self.rzedna_dna,
            "rzedna_terenu_istn": self.rzedna_terenu_istn,
            "rzedna_terenu_proj": self.rzedna_terenu_proj,
            "rzedna_dna_studni": self.rzedna_dna_studni,
            "srednica_studni_mm": self.srednica_studni_mm,
            "opis": self.opis, "dodatkowe_wloty": self.dodatkowe_wloty,
            "adnotacje": self.adnotacje,
        }


@dataclass
class OdcinekPDF:
    od: str
    do: str
    dlugosc_m: float | None = None
    dn_mm: int | None = None
    spadek_promile: float | None = None
    material: str | None = None
    rzedna_od: float | None = None
    rzedna_do: float | None = None
    surowe: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "od": self.od, "do": self.do, "dlugosc_m": self.dlugosc_m,
            "dn_mm": self.dn_mm, "spadek_promile": self.spadek_promile,
            "spadek_procent": round(self.spadek_promile / 10, 3) if self.spadek_promile is not None else None,
            "material": self.material, "rzedna_od": self.rzedna_od,
            "rzedna_do": self.rzedna_do, "surowe": self.surowe,
        }


@dataclass
class ProfilPDF:
    oznaczenie: str
    nr_strony: int
    blok_index: int
    poziom_porownawczy: float | None = None
    typ_odniesienia: str = "DNO_KANALU"
    branza: str = "KD"
    x_od: float = 0.0
    x_do: float = 0.0
    dlugosc_calkowita_m: float | None = None
    wezly: list[WezelPDF] = field(default_factory=list)
    odcinki: list[OdcinekPDF] = field(default_factory=list)
    ostrzezenia: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "oznaczenie": self.oznaczenie, "nr_strony": self.nr_strony,
            "blok_index": self.blok_index, "poziom_porownawczy": self.poziom_porownawczy,
            "typ_odniesienia": self.typ_odniesienia, "branza": self.branza,
            "dlugosc_calkowita_m": self.dlugosc_calkowita_m,
            "wezly": [w.to_dict() for w in self.wezly],
            "odcinki": [o.to_dict() for o in self.odcinki],
            "ostrzezenia": self.ostrzezenia,
        }


@dataclass
class WynikParsowania:
    profile: list[ProfilPDF] = field(default_factory=list)
    strony: list[dict] = field(default_factory=list)
    ostrzezenia: list[dict] = field(default_factory=list)

    @property
    def liczba_wezlow(self) -> int:
        return sum(len(p.wezly) for p in self.profile)

    @property
    def liczba_odcinkow(self) -> int:
        return sum(len(p.odcinki) for p in self.profile)


# ---------------------------------------------------------------- parser


class ProfileParser:
    def __init__(self, sciezka: str | Path):
        self.sciezka = Path(sciezka)
        self.wynik = WynikParsowania()

    # ---- niskopoziomowe

    @staticmethod
    def _spany(page) -> list[Span]:
        out: list[Span] = []
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b["lines"]:
                pion = abs(line["dir"][1] + 1) < 0.01
                for s in line["spans"]:
                    txt = s["text"].strip()
                    if txt:
                        out.append(Span(txt, *s["bbox"], pion))
        return out

    @staticmethod
    def _legenda(spany: list[Span]) -> dict[str, Span]:
        """Znajdz naglowki pasm w lewej kolumnie arkusza."""
        leg: dict[str, Span] = {}
        for s in spany:
            if s.pion or s.x0 > 400:
                continue
            for wzor, klucz in NAGLOWKI:
                if s.t.startswith(wzor) and klucz not in leg:
                    leg[klucz] = s
        return leg

    @staticmethod
    def _granice_pasm(leg: dict[str, Span]) -> dict[str, tuple[float, float]]:
        """Zamien pozycje naglowkow na przedzialy y dla kazdego pasma."""
        obecne = [(k, leg[k].yc) for k in KOLEJNOSC_PASM if k in leg]
        obecne.sort(key=lambda kv: kv[1])
        granice: dict[str, tuple[float, float]] = {}
        for i, (klucz, yc) in enumerate(obecne):
            gora = (obecne[i - 1][1] + yc) / 2 if i > 0 else yc - 14
            dol = (obecne[i + 1][1] + yc) / 2 if i < len(obecne) - 1 else yc + 14
            granice[klucz] = (gora, dol)
        return granice

    @staticmethod
    def _w_pasmie(s: Span, zakres: tuple[float, float]) -> bool:
        return zakres[0] <= s.yc < zakres[1]

    # ---- bloki (profile) na arkuszu

    def _bloki(self, spany: list[Span], leg: dict[str, Span]) -> list[dict]:
        """Kazdy profil ma przy lewej krawedzi nazwe + poziom porownawczy.

        Kotwica to napis "n.p.m." - jedyny pewny znacznik poczatku bloku.
        Sam "30.00m" nie wystarczy, bo tak samo wyglada dlugosc odcinka
        w pasmie SPADKI (np. "20.5m").

        Dwa warianty rozmieszczenia:
          * wieloblokowy   - "Wyl84" / "30.00m" / "n.p.m." jeden pod drugim,
          * jednoprofilowy - nazwa i "75.00 m n.p.m." w wierszu legendy.
        """
        kotwice = [s for s in spany if not s.pion and "n.p.m." in s.t and s.x0 > 250]
        kotwice.sort(key=lambda s: s.x0)

        bloki = []
        for kot in kotwice:
            m = RE_POZIOM.match(kot.t)
            if m:
                # wariant jednoprofilowy: liczba i "n.p.m." w jednym spanie
                poziom, span_poziomu = _num(m.group(1)), kot
            else:
                kand = [
                    q for q in spany
                    if not q.pion and abs(q.x0 - kot.x0) < 25
                    and kot.y0 - 28 < q.y1 <= kot.y0 + 2 and RE_POZIOM.match(q.t)
                ]
                kand.sort(key=lambda q: -q.y0)
                span_poziomu = kand[0] if kand else kot
                poziom = _num(RE_POZIOM.match(span_poziomu.t).group(1)) if kand else None

            # Nazwa profilu: poziomy span powyzej poziomu porownawczego,
            # o zblizonym x, ktory wyglada jak kod obiektu.
            kand_n = [
                q for q in spany
                if not q.pion and abs(q.x0 - span_poziomu.x0) < 50
                and span_poziomu.y0 - 28 < q.y1 <= span_poziomu.y0 + 2
                and q is not span_poziomu and "n.p.m." not in q.t
                and RE_KOD.match(q.t.replace(" ", ""))
            ]
            kand_n.sort(key=lambda q: (-q.y0, abs(q.x0 - span_poziomu.x0)))
            nazwa = kand_n[0].t.strip() if kand_n else None
            bloki.append({"x": min(kot.x0, span_poziomu.x0), "nazwa": nazwa, "poziom": poziom})

        for i, b in enumerate(bloki):
            b["x_od"] = b["x"] - 14
            b["x_do"] = bloki[i + 1]["x"] - 14 if i + 1 < len(bloki) else 1e9
        if bloki:
            bloki[0]["x_od"] = min(bloki[0]["x_od"], leg["HEKTOMETRY"].x1 + 5)
        return bloki

    @staticmethod
    def _podziel_po_pikietazu(wezly: list[WezelPDF]) -> list[list[WezelPDF]]:
        """Pikietaz w obrebie profilu zawsze rosnie.

        Spadek wartosci oznacza, ze zaczyna sie kolejny profil, ktorego naglowka
        nie udalo sie wykryc (zdarza sie, gdy napis "n.p.m." zlal sie z sasiednim).
        """
        grupy: list[list[WezelPDF]] = [[]]
        poprzedni = None
        for w in wezly:
            if (
                poprzedni is not None
                and w.hektometr is not None
                and poprzedni is not None
                and w.hektometr < poprzedni - 0.01
            ):
                grupy.append([])
            grupy[-1].append(w)
            if w.hektometr is not None:
                poprzedni = w.hektometr
        return [g for g in grupy if g]

    # ---- wezly i odcinki

    def _wezly_bloku(self, spany: list[Span], pasma: dict, blok: dict) -> list[WezelPDF]:
        zakres = pasma.get("HEKTOMETRY")
        if not zakres:
            return []
        wezly = []
        for s in spany:
            if s.pion or not self._w_pasmie(s, zakres):
                continue
            if not (blok["x_od"] <= s.x0 < blok["x_do"]):
                continue
            kod, alias = self._normalizuj_kod(s.t)
            if kod:
                wezly.append(WezelPDF(kod=kod, alias=alias, x=s.xc,
                                      bbox={"x0": s.x0, "y0": s.y0, "x1": s.x1, "y1": s.y1}))
        wezly.sort(key=lambda w: w.x)
        return wezly

    @staticmethod
    def _normalizuj_kod(txt: str) -> tuple[str | None, str | None]:
        """'S.S.S.Wp253' -> 'Wp253'; 'KT15=D139' -> ('KT15', 'D139')."""
        t = txt.strip().replace(" ", "")
        alias = None
        m = RE_KOD_ALIAS.match(t)
        if m:
            t, alias_raw = m.group(1), m.group(2)
            a = RE_KOD.match(alias_raw)
            alias = f"{a.group(1)}{a.group(2)}" if a else alias_raw
        m = RE_KOD.match(t)
        if not m:
            return None, None
        prefiks = m.group(1)
        # ujednolic wielkosc liter: Wyl / Wp / SEP / Tr / KT / D / O
        mapa = {"wyl": "Wyl", "wp": "Wp", "ws": "Ws", "wo": "Wo", "sep": "SEP",
                "tr": "Tr", "kt": "KT", "ł": "Ł", "l": "Ł", "d": "D", "o": "O"}
        return f"{mapa.get(prefiks.lower(), prefiks)}{m.group(2)}", alias

    def _kandydaci(self, spany, pasma, blok, klucz) -> list[Span]:
        zakres = pasma.get(klucz)
        if not zakres:
            return []
        out = [
            s for s in spany
            if s.pion and self._w_pasmie(s, zakres)
            and blok["x_od"] <= s.x0 < blok["x_do"] and RE_LICZBA.match(s.t)
        ]
        out.sort(key=lambda s: s.x0)
        return out

    def _przypisz_wartosci(self, spany, pasma, blok, wezly: list[WezelPDF], prof: ProfilPDF):
        """Przypisz pionowe wartosci z pasm do kolumn wezlow.

        Wezel z kilkoma doplywami ma w pasmach DNO i ZAGLEBIENIE wiecej niz
        jedna wartosc (kazdy wlot na innej rzednej). Wlasciwa pare wybieramy
        przez zweryfikowany niezmiennik:

            zaglebienie = rzedna terenu proj. - rzedna dna

        Pozostale pary trafiaja do listy dodatkowych wlotow.
        """
        if not wezly:
            return

        kosze: dict[str, dict[int, list[float]]] = {}
        for klucz in ("TEREN_PROJ", "TEREN_ISTN", "DNO", "ZAGLEBIENIE", "ODLEGLOSCI"):
            kosze[klucz] = {i: [] for i in range(len(wezly))}
            for s in self._kandydaci(spany, pasma, blok, klucz):
                i = min(range(len(wezly)), key=lambda k: abs(wezly[k].x - s.xc))
                if abs(wezly[i].x - s.xc) <= TOL_X_WEZEL:
                    kosze[klucz][i].append(_num(s.t))

        poprzedni_hm = None
        for i, w in enumerate(wezly):
            tp = kosze["TEREN_PROJ"][i]
            ti = kosze["TEREN_ISTN"][i]
            dna = kosze["DNO"][i]
            zag = kosze["ZAGLEBIENIE"][i]
            hm = kosze["ODLEGLOSCI"][i]

            w.rzedna_terenu_istn = ti[0] if ti else None

            # Pikietaz: wybierz wartosc niemalejaca wzgledem poprzedniego wezla.
            if hm:
                rosnace = [v for v in hm if poprzedni_hm is None or v >= poprzedni_hm - 0.01]
                w.hektometr = rosnace[0] if rosnace else hm[0]
                poprzedni_hm = w.hektometr

            # Trojka (teren proj., dno, zaglebienie) najlepiej spelniajaca niezmiennik.
            najlepsza, blad_najl = None, None
            for a in tp or [None]:
                for b in dna or [None]:
                    for c in zag or [None]:
                        if None in (a, b, c):
                            continue
                        blad = abs(a - b - c)
                        if blad_najl is None or blad < blad_najl:
                            najlepsza, blad_najl = (a, b, c), blad
            if najlepsza and blad_najl is not None and blad_najl <= 0.015:
                w.rzedna_terenu_proj, w.rzedna_dna, w.zaglebienie = najlepsza
            else:
                w.rzedna_terenu_proj = tp[0] if tp else None
                w.rzedna_dna = dna[0] if dna else None
                w.zaglebienie = zag[0] if zag else None
                if blad_najl is not None:
                    prof.ostrzezenia.append(
                        f"{w.kod}: nie znaleziono trojki spelniajacej niezmiennik "
                        f"(najlepszy blad {round(blad_najl, 3)} m)"
                    )

            # Nadmiarowe rzedne dna = dodatkowe wloty do wezla.
            for v in dna:
                if v != w.rzedna_dna:
                    w.dodatkowe_wloty.append(v)

        # Opisy obiektow: pionowe spany konczace sie tuz nad pierwszym pasmem danych.
        gora_tabeli = pasma.get("TEREN_PROJ", (0, 0))[0]
        opisy = [
            s for s in spany
            if s.pion and blok["x_od"] <= s.x0 < blok["x_do"]
            and gora_tabeli - 22 < s.y1 <= gora_tabeli + 2 and not RE_LICZBA.match(s.t)
        ]
        for s in opisy:
            blisko = min(wezly, key=lambda w: abs(w.x - s.xc))
            if abs(blisko.x - s.xc) >= TOL_X_WEZEL:
                continue
            niski = s.t.lower()
            if any(k in niski for k in ADNOTACJA):
                # To adnotacja o przylaczu, nie opis wezla - Rz.d. jest tu
                # rzedna wlotu, a nie dnem studni.
                blisko.adnotacje.append(s.t)
                continue
            if blisko.opis and not any(niski.startswith(k) for k in OPIS_OBIEKTU):
                continue
            blisko.opis = s.t
            if (m := RE_RZ_STUDNI.search(s.t)):
                blisko.rzedna_dna_studni = _num(m.group(1))
            if (m := RE_DN_STUDNI.search(s.t)):
                blisko.srednica_studni_mm = int(m.group(1))

        # Adnotacje z rysunku (wlaczenia, skrzyzowania) - powyzej tabeli.
        adn = [
            s for s in spany
            if s.pion and blok["x_od"] <= s.x0 < blok["x_do"]
            and s.y1 <= gora_tabeli - 22 and len(s.t) > 8
        ]
        for s in adn:
            blisko = min(wezly, key=lambda w: abs(w.x - s.xc))
            if abs(blisko.x - s.xc) < TOL_X_WEZEL * 2:
                blisko.adnotacje.append(s.t)

    def _odcinki_bloku(self, spany, pasma, blok, wezly: list[WezelPDF]) -> list[OdcinekPDF]:
        odcinki = []
        for i in range(len(wezly) - 1):
            a, b = wezly[i], wezly[i + 1]
            lo, hi = a.x, b.x
            odc = OdcinekPDF(od=a.kod, do=b.kod)
            surowe: dict[str, list[str]] = {}

            for klucz in ("SPADKI", "SREDNICA", "ODLEGLOSCI"):
                zakres = pasma.get(klucz)
                if not zakres:
                    continue
                miedzy = [
                    s for s in spany
                    if not s.pion and self._w_pasmie(s, zakres) and lo < s.xc < hi
                ]
                surowe[klucz] = [s.t for s in miedzy]
                for s in miedzy:
                    self._czytaj_atrybut_odcinka(odc, s.t, klucz)

            # Dlugosc: gdy brak jawnej, licz z pikietazu.
            if odc.dlugosc_m is None and a.hektometr is not None and b.hektometr is not None:
                odc.dlugosc_m = round(abs(b.hektometr - a.hektometr), 2)

            odc.rzedna_od = a.rzedna_dna
            odc.rzedna_do = b.rzedna_dna
            odc.surowe = surowe
            odcinki.append(odc)
        return odcinki

    @staticmethod
    def _czytaj_atrybut_odcinka(odc: OdcinekPDF, txt: str, pasmo: str) -> None:
        if (m := RE_SREDNICA.search(txt)) and odc.dn_mm is None:
            odc.dn_mm = int(m.group(1))
        if (m := RE_DLUGOSC.search(txt)) and odc.dlugosc_m is None:
            odc.dlugosc_m = _num(m.group(1))
        if pasmo == "SPADKI":
            if (m := RE_SPADEK.match(txt)) and odc.spadek_promile is None:
                v = _num(m.group(1))
                odc.spadek_promile = round(v * 10, 3) if v is not None else None
            elif (m := RE_DLUGOSC_SAMA.match(txt)) and odc.dlugosc_m is None:
                odc.dlugosc_m = _num(m.group(1))
        if pasmo == "ODLEGLOSCI" and odc.dlugosc_m is None and RE_LICZBA.match(txt):
            odc.dlugosc_m = _num(txt)
        for mat in ("PP", "PE", "PVC", "BET", "GRP", "kamionka", "żeliwo"):
            if mat.lower() in txt.lower() and odc.material is None:
                odc.material = mat

    # ---- publiczne

    def parsuj(self) -> WynikParsowania:
        doc = fitz.open(self.sciezka)
        for nr in range(doc.page_count):
            page = doc[nr]
            spany = self._spany(page)
            leg = self._legenda(spany)
            if "HEKTOMETRY" not in leg:
                self.wynik.ostrzezenia.append(
                    {"strona": nr + 1, "problem": "brak legendy pasm - strona pominieta"}
                )
                continue

            pasma = self._granice_pasm(leg)
            os_przewodu = any(
                s.t.startswith("RZĘDNA OSI PRZEWODU") for s in spany if not s.pion and s.x0 < 400
            )
            typ_odn = "OS_PRZEWODU" if os_przewodu else "DNO_KANALU"

            self.wynik.strony.append({
                "nr_strony": nr + 1,
                "szerokosc": round(page.rect.width, 2),
                "wysokosc": round(page.rect.height, 2),
                "typ_odniesienia": typ_odn,
                "liczba_spanow": len(spany),
            })

            bloki = self._bloki(spany, leg)
            if not bloki:
                # Jeden profil na cala strone - wartosc legendy w tym samym wierszu.
                bloki = [{"x": leg["OZNACZENIE"].x1, "x_od": leg["OZNACZENIE"].x1,
                          "x_do": 1e9, "nazwa": None, "poziom": None, "span": None}]

            for idx, blok in enumerate(bloki):
                wezly = self._wezly_bloku(spany, pasma, blok)
                if not wezly:
                    continue
                zbior_ostrzezen = ProfilPDF(oznaczenie="tmp", nr_strony=nr + 1, blok_index=idx)
                self._przypisz_wartosci(spany, pasma, blok, wezly, zbior_ostrzezen)

                # Blok moze zawierac wiecej niz jeden profil, jesli naglowek
                # sasiada nie zostal wykryty - rozpoznajemy to po resecie pikietazu.
                for j, grupa in enumerate(self._podziel_po_pikietazu(wezly)):
                    nazwa = blok["nazwa"] if j == 0 and blok["nazwa"] else grupa[-1].kod
                    kod_n, _ = self._normalizuj_kod(nazwa)
                    prof = ProfilPDF(
                        oznaczenie=kod_n or nazwa,
                        nr_strony=nr + 1,
                        blok_index=idx * 100 + j,
                        poziom_porownawczy=blok["poziom"],
                        typ_odniesienia=typ_odn,
                        branza="KT" if typ_odn == "OS_PRZEWODU" else "KD",
                        x_od=grupa[0].x,
                        x_do=min(grupa[-1].x, page.rect.width),
                    )
                    if j == 0:
                        prof.ostrzezenia.extend(zbior_ostrzezen.ostrzezenia)
                    prof.wezly = grupa
                    prof.odcinki = self._odcinki_bloku(spany, pasma, blok, grupa)
                    dl = [o.dlugosc_m for o in prof.odcinki if o.dlugosc_m]
                    prof.dlugosc_calkowita_m = round(sum(dl), 2) if dl else None
                    self._waliduj(prof)
                    self.wynik.profile.append(prof)

        doc.close()
        return self.wynik

    @staticmethod
    def _waliduj(prof: ProfilPDF) -> None:
        """Niezmienniki projektowe - rozbieznosci lecza do raportu, nie do wyjatku."""
        for w in prof.wezly:
            if None not in (w.rzedna_terenu_proj, w.rzedna_dna, w.zaglebienie):
                oczek = round(w.rzedna_terenu_proj - w.rzedna_dna, 2)
                if abs(oczek - w.zaglebienie) > 0.015:
                    prof.ostrzezenia.append(
                        f"{w.kod}: zaglebienie {w.zaglebienie} != "
                        f"RTproj-Rzdna {oczek} (roznica {round(oczek - w.zaglebienie, 3)})"
                    )
            if w.rzedna_dna_studni is not None and w.rzedna_dna is not None:
                if w.rzedna_dna_studni > w.rzedna_dna + 0.001:
                    prof.ostrzezenia.append(
                        f"{w.kod}: dno studni {w.rzedna_dna_studni} powyzej dna kanalu {w.rzedna_dna}"
                    )
        for o in prof.odcinki:
            rz_od, rz_do = o.rzedna_od, o.rzedna_do
            if None in (rz_od, rz_do) or not o.dlugosc_m or o.spadek_promile is None:
                continue
            # Profile rysuje sie zwykle od wylotu w gore zlewni, wiec dno rosnie
            # wzdluz rysunku. Kierunek zapisujemy osobno, a spadek porownujemy
            # co do wartosci bezwzglednej.
            wylicz = (rz_od - rz_do) / o.dlugosc_m * 1000
            o.surowe["kierunek_rysunku"] = "z_pradem" if wylicz >= 0 else "pod_prad"
            if abs(abs(wylicz) - abs(o.spadek_promile)) > max(1.0, abs(o.spadek_promile) * 0.15):
                prof.ostrzezenia.append(
                    f"{o.od}-{o.do}: spadek z rysunku {abs(o.spadek_promile)}‰ vs "
                    f"z rzednych {abs(round(wylicz, 2))}‰ (dl. {o.dlugosc_m} m)"
                )


def parsuj_profile(sciezka: str | Path) -> WynikParsowania:
    return ProfileParser(sciezka).parsuj()
