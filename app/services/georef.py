"""Zwiazanie arkusza planu z ukladem panstwowym.

Problem
-------
Plan sytuacyjny nie niesie zadnej informacji o wspolrzednych: nie ma warstw,
nie ma metadanych, nie ma nawet siatki krzyzy, po ktorej dalo by sie odczytac
uklad (sprawdzone - na zadnej z 18 stron). Tabelka podaje tylko nazwe ukladu:
"2000/15", czyli **PL-2000 strefa 5** (poludnik 15 stopni E, EPSG:2176), zgodnie
z plikiem osnowy, gdzie X to ok. 5,77 mln, a Y ok. 5,50 mln.

Rozwiazanie
-----------
Skoro rysunek nie powie nam, gdzie lezy, musi to powiedziec czlowiek - ale
wystarczy **dwa razy**. Wskazujesz na mapie dwa punkty, ktorych wspolrzedne
znamy (najlepiej repery z osnowy), a reszte program dolicza sam.

Dlaczego przeksztalcenie Helmerta, a nie dowolne afiniczne
----------------------------------------------------------
Rysunek w skali 1:1000 jest podobienstwem terenu: obrot, przesuniecie i jedna
wspolna skala. Przeksztalcenie afiniczne dopuszcza rozna skale w obu osiach
i scinanie - dopasowaloby sie lepiej do bledow wskazania i **ukrylo** je,
zamiast pokazac. Helmert ma tylko 4 niewiadome, wiec kazde niedokladne
wskazanie od razu widac w odchylce.

Kontrola
--------
Dwa punkty daja dopasowanie idealne z definicji (4 rownania, 4 niewiadome),
wiec ich odchylka zawsze wynosi zero i nic nie mowi. Dopiero **trzeci punkt**
jest sprawdzianem. Dlatego skala i obrot sa zawsze pokazywane obok wyniku:
skala musi wyjsc ok. 0,3528 m na punkt. Jesli nie wychodzi, wskazania sa
pomylone i lepiej to zobaczyc od razu.

Uklad wspolrzednych
-------------------
W PDF os Y rosnie w dol, w geodezji do gory - stad odwrocenie znaku. W PL-2000
X to polnoc, Y to wschod (odwrotnie niz w matematyce), wiec nazwy zmiennych
trzymaja sie konwencji geodezyjnej, nie matematycznej.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Skala 1:1000 -> 1 pt (1/72 cala) = 0,352778 mm na papierze = tyle metrow w terenie.
METRY_NA_PUNKT_1_1000 = 25.4 / 72.0

# Ile skala z dopasowania moze odbiegac od skali rysunku, zanim uznamy,
# ze wskazania sa pomylone. 5% to juz 50 m bledu na kilometrze.
TOL_SKALI = 0.05
TOL_ODCHYLKI_M = 1.0


@dataclass(frozen=True)
class Kotwica:
    """Punkt o znanych wspolrzednych wskazany na rysunku."""

    x_pt: float
    y_pt: float
    x_gis: float          # polnoc (northing)
    y_gis: float          # wschod (easting)
    nazwa: str = ""


@dataclass(frozen=True)
class Przeksztalcenie:
    """Przeliczenie punktu PDF na wspolrzedne panstwowe.

        Y (wschod)  = ey_x * x + ey_y * y + ey_0
        X (polnoc)  = nx_x * x + nx_y * y + nx_0
    """

    ey_x: float
    ey_y: float
    ey_0: float
    nx_x: float
    nx_y: float
    nx_0: float

    skala_m_na_pt: float
    obrot_stopnie: float
    rmse_m: float
    liczba_kotwic: int
    kontrola: list[dict]

    # ------------------------------------------------------------ uzycie

    def na_teren(self, x_pt: float, y_pt: float) -> tuple[float, float]:
        """Punkt na rysunku -> (X polnoc, Y wschod) w PL-2000."""
        y_gis = self.ey_x * x_pt + self.ey_y * y_pt + self.ey_0
        x_gis = self.nx_x * x_pt + self.nx_y * y_pt + self.nx_0
        return round(x_gis, 3), round(y_gis, 3)

    def na_rysunek(self, x_gis: float, y_gis: float) -> tuple[float, float]:
        """(X polnoc, Y wschod) -> punkt na rysunku. Odwrocenie podobienstwa."""
        a, b = self.ey_x, self.ey_y
        wyznacznik = a * a + b * b
        if wyznacznik == 0:
            raise ValueError("Przeksztalcenie zdegenerowane - zerowa skala.")
        de = y_gis - self.ey_0
        dn = x_gis - self.nx_0
        # Odwrotnosc macierzy [[a, b], [b, -a]] to (1/(a^2+b^2)) * [[a, b], [b, -a]].
        x_pt = (a * de + b * dn) / wyznacznik
        y_pt = (b * de - a * dn) / wyznacznik
        return round(x_pt, 2), round(y_pt, 2)

    @property
    def skala_rysunku(self) -> int:
        """Mianownik skali, np. 1000 dla 1:1000."""
        return int(round(self.skala_m_na_pt / METRY_NA_PUNKT_1_1000 * 1000))

    @property
    def wiarygodne(self) -> bool:
        """Czy dopasowanie w ogole ma sens.

        Zgodnosc skali jest tu wazniejsza od odchylki: przy dwoch kotwicach
        odchylka z definicji wynosi zero, a skala i tak wychodzi bledna,
        gdy ktores wskazanie trafilo w zly punkt.
        """
        if abs(self.skala_m_na_pt - METRY_NA_PUNKT_1_1000) / METRY_NA_PUNKT_1_1000 > TOL_SKALI:
            return False
        return self.rmse_m <= TOL_ODCHYLKI_M

    def to_dict(self) -> dict:
        return {
            "wspolczynniki": [self.ey_x, self.ey_y, self.ey_0,
                              self.nx_x, self.nx_y, self.nx_0],
            "skala_m_na_pt": round(self.skala_m_na_pt, 6),
            "skala_rysunku": self.skala_rysunku,
            "obrot_stopnie": round(self.obrot_stopnie, 4),
            "rmse_m": round(self.rmse_m, 3),
            "liczba_kotwic": self.liczba_kotwic,
            "wiarygodne": self.wiarygodne,
            "kontrola": self.kontrola,
        }


def dopasuj(kotwice: list[Kotwica]) -> Przeksztalcenie:
    """Dopasuj podobienstwo do wskazanych punktow (najmniejsze kwadraty).

    Zamkniety wzor Helmerta - bez macierzy i bez numpy, bo niewiadome sa tylko
    cztery, a przejrzystosc jest tu wazniejsza niz ogolnosc.
    """
    if len(kotwice) < 2:
        raise ValueError("Do zwiazania arkusza z terenem potrzebne sa co najmniej "
                         "dwa punkty o znanych wspolrzednych.")

    # W PDF os Y rosnie w dol - odwracamy ja, zeby uklad byl prawoskretny.
    u = [k.x_pt for k in kotwice]
    v = [-k.y_pt for k in kotwice]
    e = [k.y_gis for k in kotwice]      # wschod
    n = [k.x_gis for k in kotwice]      # polnoc

    ile = len(kotwice)
    su, sv = sum(u) / ile, sum(v) / ile
    se, sn = sum(e) / ile, sum(n) / ile

    du = [w - su for w in u]
    dv = [w - sv for w in v]
    de = [w - se for w in e]
    dn = [w - sn for w in n]

    mianownik = sum(a * a + b * b for a, b in zip(du, dv))
    if mianownik == 0:
        raise ValueError("Wskazane punkty leza w tym samym miejscu na rysunku.")

    a = sum(x * p + y * q for x, y, p, q in zip(du, dv, de, dn)) / mianownik
    b = sum(x * q - y * p for x, y, p, q in zip(du, dv, de, dn)) / mianownik
    c = se - a * su + b * sv
    d = sn - b * su - a * sv

    # Zlozenie odwrocenia osi Y ze wzorem podobienstwa (v = -y):
    #   E = a*x + b*y + c
    #   N = b*x - a*y + d
    skala = math.hypot(a, b)
    obrot = math.degrees(math.atan2(b, a))

    kontrola: list[dict] = []
    suma_kwadratow = 0.0
    for kotwica in kotwice:
        y_lic = a * kotwica.x_pt + b * kotwica.y_pt + c
        x_lic = b * kotwica.x_pt - a * kotwica.y_pt + d
        odchylka = math.hypot(x_lic - kotwica.x_gis, y_lic - kotwica.y_gis)
        suma_kwadratow += odchylka ** 2
        kontrola.append({
            "nazwa": kotwica.nazwa,
            "odchylka_m": round(odchylka, 3),
            "x_gis": kotwica.x_gis,
            "y_gis": kotwica.y_gis,
        })

    return Przeksztalcenie(
        ey_x=a, ey_y=b, ey_0=c, nx_x=b, nx_y=-a, nx_0=d,
        skala_m_na_pt=skala,
        obrot_stopnie=obrot,
        rmse_m=math.sqrt(suma_kwadratow / ile),
        liczba_kotwic=ile,
        kontrola=kontrola,
    )


def z_wspolczynnikow(wsp: list[float], skala: float = 0.0, obrot: float = 0.0,
                     rmse: float = 0.0, kotwic: int = 0) -> Przeksztalcenie:
    """Odtworz przeksztalcenie zapisane w bazie."""
    ey_x, ey_y, ey_0, nx_x, nx_y, nx_0 = (float(w) for w in wsp)
    return Przeksztalcenie(
        ey_x=ey_x, ey_y=ey_y, ey_0=ey_0, nx_x=nx_x, nx_y=nx_y, nx_0=nx_0,
        skala_m_na_pt=skala or math.hypot(ey_x, ey_y),
        obrot_stopnie=obrot or math.degrees(math.atan2(ey_y, ey_x)),
        rmse_m=rmse, liczba_kotwic=kotwic, kontrola=[],
    )


def odleglosc_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Odleglosc w terenie miedzy dwoma punktami (X polnoc, Y wschod)."""
    return round(math.hypot(a[0] - b[0], a[1] - b[1]), 2)


def plik_swiata(przeksztalcenie: Przeksztalcenie, dpi: int,
                clip_x0: float = 0.0, clip_y0: float = 0.0) -> str:
    """Zawartosc pliku ".pgw" - dzieki niemu PNG otwiera sie w QGIS na miejscu.

    Plik swiata opisuje, jak piksel obrazu przeklada sie na teren. Kolejnosc
    wierszy narzuca format: A, D, B, E, C, F.
    """
    pt_na_piksel = 72.0 / dpi
    a = przeksztalcenie.ey_x * pt_na_piksel      # zmiana wschodu na piksel w prawo
    d = przeksztalcenie.nx_x * pt_na_piksel      # zmiana polnocy na piksel w prawo
    b = przeksztalcenie.ey_y * pt_na_piksel      # zmiana wschodu na piksel w dol
    e = przeksztalcenie.nx_y * pt_na_piksel      # zmiana polnocy na piksel w dol
    # Srodek lewego gornego piksela wycinka.
    x_gis, y_gis = przeksztalcenie.na_teren(clip_x0 + pt_na_piksel / 2,
                                            clip_y0 + pt_na_piksel / 2)
    return "\n".join(f"{w:.10f}" for w in (a, d, b, e, y_gis, x_gis)) + "\n"
