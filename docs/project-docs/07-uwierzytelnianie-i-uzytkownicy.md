# Logowanie, konta i zadania

---

## Zasada

Narzędzie zawiera dane wykonawcze konkretnej budowy, więc **cały interfejs jest
za logowaniem**. Bez sesji każdy adres przekierowuje na `/login`.

Wyjątki — świadome i krótkie:

| Endpoint | Dlaczego otwarty |
|---|---|
| `/login` | inaczej nie dałoby się zalogować |
| `/static/…` | arkusze stylów i skrypty ekranu logowania |
| `/api/zdrowie` | monitoring kontenera musi działać bez sesji |

Realizacja: `before_request` w `app/__init__.py` plus lista `JAWNE`
w `app/blueprints/auth.py`.

---

## Konto startowe

```bash
docker compose exec web python -m flask utworz-admina
```

Tworzy konto **`budowa-adm`** z rolą ADMIN i **losowym hasłem**
(`secrets.token_urlsafe`). Hasło:

- trafia do bazy **wyłącznie jako skrót** (`werkzeug.security`) — jawnego nie da
  się odczytać nawet z bazy,
- jest dopisywane do pliku `.env` jako `ADMIN_HASLO` (plik jest w `.gitignore`),
- wypisuje się raz na ekranie.

Zmiana hasła:
```bash
docker compose exec web python -m flask zmien-haslo budowa-adm
docker compose exec web python -m flask lista-kont
```

---

## Role

| | ADMIN | KIEROWNIK | BRYGADZISTA | MONTER |
|---|:--:|:--:|:--:|:--:|
| podgląd danych, wyszukiwarka, niwelator | ✔ | ✔ | ✔ | ✔ |
| pomiar wykonawczy | ✔ | ✔ | ✔ | ✔ |
| stan odcinka: wytyczony / w trakcie | ✔ | ✔ | ✔ | ✔ |
| zgłoszenie odcinka jako **wykonany** | ✔ | ✔ | ✔ | ✔ |
| **odbiór** odcinka i cofnięcie odbioru | ✔ | ✔ | — | — |
| raport dzienny — własny | ✔ | ✔ | ✔ | ✔ |
| raport dzienny — podgląd cudzych | ✔ | ✔ | ✔ | — |
| przydzielanie zadań innym | ✔ | ✔ | — | — |
| zarządzanie kontami | ✔ | — | — | — |

Rolę zmienia się w panelu (`/panel/uzytkownicy`) albo bezpośrednio w bazie.

### Dlaczego monter to osobna rola

Różnica monter ↔ brygadzista jest jedna i konkretna: **monter widzi tylko swoje
raporty**. Reszta pracy w wykopie jest ta sama, bo w wykopie stoją obok siebie.

Podział przebiega tam, gdzie przebiega na budowie: **zgłosić wykonanie może
każdy, kto tę robotę zrobił — odebrać może tylko kierownik**. Stąd dwa osobne
stany odcinka, WYKONANY i ODEBRANY.

### Uprawnienia w kodzie

Widoki pytają o **możliwość**, nie o rolę:

```python
current_user.moze_odbierac          # ADMIN, KIEROWNIK
current_user.moze_przydzielac       # ADMIN, KIEROWNIK
current_user.widzi_cudze_raporty    # wszyscy poza monterem
current_user.jest_adminem
```

Dzięki temu zmiana zakresu uprawnień to poprawka w `app/models/user.py`,
a nie polowanie na `rola ==` po szablonach.

⚠️ **Reguły działają po stronie serwera, nie tylko w interfejsie.** Przycisk
odbioru jest ukrywany monterowi, ale gdyby ktoś wysłał żądanie z pominięciem
strony, `wolno_ustawic()` i tak je odrzuci. Pilnuje tego
`test_monter_zglasza_ale_nie_odbiera`.

### Dopisanie roli wymaga zmiany w bazie

`db.create_all()` tworzy typ wyliczeniowy raz i nigdy go nie rusza, więc nowa
rola w Pythonie **nie pojawi się w Postgresie** — przy pierwszym zapisie wyszedłby
błąd „invalid input value for enum". Wartości dokłada `app/services/schemat.py`
przez `ALTER TYPE rola ADD VALUE IF NOT EXISTS`, uruchamiane przy `flask init-db`.

Ta operacja jest **nieodwracalna** — Postgres nie ma `DROP VALUE`. Literówka
oznacza przebudowę typu.

---

## Panel użytkowników

`/panel/uzytkownicy` — dostępny tylko dla roli ADMIN.

- **Zakładanie kont** — hasło można podać albo zostawić puste, wtedy zostanie
  wygenerowane. Pokazuje się **tylko raz**, zaraz po utworzeniu.
- **Reset hasła** — generuje nowe i pokazuje raz.
- **Włączanie i wyłączanie kont** — wyłączone konto nie może się zalogować,
  ale zostaje w historii zadań.
- **Zmiana roli**.

Dwa zabezpieczenia wbudowane w panel: nie da się wyłączyć własnego konta ani
ostatniego aktywnego administratora — w obu przypadkach zostałby zamknięty
dostęp do panelu.

---

## Zadania

`/zadania`

**Zadanie bez przypisanej osoby jest globalne** — widzi je cała ekipa.
Przypisane widzi tylko właściciel oraz kierownictwo.

Każde zadanie może wskazywać element sieci:

| Wpis w polu „Dotyczy” | Efekt |
|---|---|
| `D155` | powiązanie z obiektem |
| `Wyl101-D155` | powiązanie z odcinkiem |

Pola: tytuł, opis, priorytet (niski / zwykły / wysoki / pilny), termin, status
(nowe / w trakcie / zrobione / anulowane).

Zadania po terminie są podświetlane. Licznik otwartych zadań (własnych
i globalnych) pokazuje się w pasku nawigacji na każdej stronie.

Usunąć zadanie może jego autor albo administrator.

### API

```
GET  /api/zadania?zakres=moje|globalne|wszystkie
POST /zadania/dodaj
POST /zadania/<id>/status
POST /zadania/<id>/usun
```

---

## Bezpieczeństwo — co jest zrobione

- Hasła wyłącznie jako skrót (`generate_password_hash` / `check_password_hash`).
- Komunikat przy błędnym logowaniu **nie zdradza**, czy pomylono login, czy hasło.
- Ochrona przed otwartym przekierowaniem: parametr `?next=` przyjmuje wyłącznie
  ścieżki względne — `https://obcy.example/…` zostanie odrzucone.
- Ciasteczko sesji: `HttpOnly` i `SameSite=Lax`.
- Konto wyłączone nie przechodzi logowania (`is_active` z Flask-Login).

## Czego brakuje do wystawienia w internet

To narzędzie jest projektowane do pracy w sieci budowy. Zanim trafi do
publicznego internetu, trzeba dołożyć:

- **HTTPS** — bez tego hasło leci otwartym tekstem; do tego `SESSION_COOKIE_SECURE`,
- **ochronę CSRF** dla formularzy POST (np. Flask-WTF),
- **ograniczenie liczby prób logowania** (rate limiting),
- **własny `SECRET_KEY`** w `.env` — domyślny `dev-secret-change-me`
  unieważnia podpis sesji.
