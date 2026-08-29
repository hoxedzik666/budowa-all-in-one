[###START ANALISE AND PREPARE###]
Wciel sie w role backend developera ktory programuje interaktywne narzedzie dla kierownikow budow oraz brygadzistow w branzy wod-kan

Projekt ktory bedziemy tworzyc oparty zosyanie o technologie backend Flask, oraz obsluge bazy danych ktora wybierzemuy po twojej analizie i dobraniu najszybszej opcji za front-end odpowiadac bedzie bootstrap5 / tailwind-css oraz jquery. ~ caly projekt powinien opierac sie na strukturze docker'a 

- stworz strukture projektu Flask oparta na dockerze oraz postdegre DB. 
- dodaj pliki tailwinds-css / jquery / bootstrap5 

nastepnie przeanaliuj internet oraz swoje dostepne zrodla w celu uzyskaniu informacji o korzysyaniu z niwelatora, potrzebnych danych do obliczen w branzy wod-kan, czm jest reper, czym jest rzedna projektowa,rzedna dna kanalu

- w folderze docs/sonnet-think-output -> rozpisz mi co znalazles na ten temat oraz jak to rozumiesz

Przeanalizuj pliki znajdujace sie w folderze docs. Sprobuj je zrozumiec szczegolnbie plik "profile scalobne.pdf"
zrozum logike pliku oraz naucz sie odczytywac z niego dane 

Wyl101 - D155 miedzy nimi podana jest ilosc metrow 

Ø500 - oznacza srednice uzytej rury

0.3% - spadek liczony procentowo. 

^ napisz mi plik .md w docs/sonnet-think-output jak rozumiesz przeanalizowane dane. pamietaj ze np wyl01-d155 to odcinek. kazdy odcinek powinienes interpretowac innaczej, oraz kazdy obiekt w pliku np wyl101 - rowniez osobno.

wyl <- wylot
D <- studnia 
wp <- wpust
SEP <- sepatator
O <- osadnik 

jesli trafisz na cos czego nie bedziesz w stanie zrozumiec zadaj mi pytanie.

[###START PROMPT###]

twoim pierwszym zadaniem bedzie podzielenie pliku "profile scalone.pdf" na pojedyncze obiekty zczytanie danych z tego pliku i przypisanie kazdwemu obiektowi wlasnych, oraz odnotowanie tego ze np wyl101 - d155 sa odcinkiem i zapisanie tego w nowo utworzonej bazie danych postdegre z poprzednich krokow. 


[### PREPARE ###]

Przygotuj sie do tego ze po kazdym kolejnym kroku w wykonaniu projektu oraz na temat jego dzialania, uzytnych technologii,instrukcji obslugi bedziesz tworzc dokumentacje techniczna jako pliki .md w folderze docs/project-docs 

~ dodaj informacje o tym ze rury posiadane przez wykonawce maja dlugosc 3m oraz 6m

[ ### END PREPARE ###]

[START PROMPT]

caly projekt bedzie intearaktywna strona pozwalajaca miedzy innymi na wyszukiwanie informacji oraz wyswietlanie rysunku z profilu przez wyszukiwarke zawarta w formularzu na stronie. 

jesli wyszukam d155 znaleziony dla mnie zostanie caly odcinek wraz z informacjami o np wylocie ktory jest zawarty w tym odcinku zostanie mi przerysowany obrazek wraz z tabelka dla tego dcinka z profilu, z plikow Material.xlsx <-- wykaz uzytych do tego odcinka potrzebnych materialow.  (TO JUZ JEST ALE NIE CALOSCIOWO)

z pliku Plany Sytuacyjne Scalone odszukaj informacje o kilometrze, oraz przedstaw mapke odcinka  
obliczaj ile rur jest potrzebne w wariancie 

- same 3metrowe 

- same 6metrowe

- mieszanym

jesli zapotrzebowanie na rure bedzie mniejsze niz dostepne opcje uznaj reszte za
docinke i wypisz ile docinki bedzie potrzebne. 

znajdz z planu rowniez najblizsze repery tam wystepujace etc. chce bardziej dokladne informacje miedzy odcinkami.


[fix]
kiedy chce wyswietlic uwagi w http://localhost:8000/importy --> odrazu one znikaja. 
nawikacja nie wyswietla sie  w trybie pelno-ekranowyum duze ekrany 
nawigacja zniika w wersji na urzadzenia mobilne.  
[end-fix]
[prompt]
dodaj opcje wyliczenia calego spadku na ciagu rur biorac pod uwage niwelator, korzystajac z rzeczywistego spadku po odjeciu srednic studni8i na odcinku. Jako dane popros rowniez o rzeczywista wysokosc dna kanalu, wysokosc od cieku rury do gornego karba. (tam gdzie monter moze polozyc late) -> wyliczaj spadek do konca odcinka i podawaj to co ma zobaczyc osoba na niwelatorze kiedy monter polozy juz late. 

dodaj rozne motywy graficzne. 

na stronie glownej dodaj mozliwosc wyswietlnia podgladu planu 
przygotuj strone pod przejscie na panel logowania [nie chcemy aby nikt obcy korzystal z panelu username: budowa-adm / haslo: wygeneruj i podaj. ]

Dodaj takze panel uzytkownika narazie pozwol w nim tworzyc nowych userow. oraz przygotuj sie do przygotowania todo list systemu ktory pozwoli dodawac zadania globalnie lub dla poszczegolnych kont
[/prompt]
[prepare]

przygotuj dokumentacje techniczna na temat dzialania projektu (co robia poszczegolne skrypty - struktury i dzialania folderow oraz ich przeznaczenia.)
[/prepare] 

[FIX] 
    2026-08-29 20:29:02.166 | Error: While importing 'wsgi', an ImportError was raised:
    2026-08-29 20:29:02.166 | 
    2026-08-29 20:29:02.166 | Traceback (most recent call last):
    2026-08-29 20:29:02.166 |   File "/usr/local/lib/python3.12/site-packages/flask/cli.py", line 245, in locate_app
    2026-08-29 20:29:02.166 |     __import__(module_name)
    2026-08-29 20:29:02.166 |   File "/srv/app/wsgi.py", line 2, in <module>
    2026-08-29 20:29:02.166 |     from app import create_app
    2026-08-29 20:29:02.166 |   File "/srv/app/app/__init__.py", line 7, in <module>
    2026-08-29 20:29:02.166 |     from flask_login import current_user
    2026-08-29 20:29:02.166 | ModuleNotFoundError: No module named 'flask_login'
    2026-08-29 20:29:02.166 | 
    2026-08-29 20:29:02.166 | 
    2026-08-29 20:29:02.167 | Usage: python -m flask [OPTIONS] COMMAND [ARGS]...
    2026-08-29 20:29:02.167 | Try 'python -m flask --help' for help.
    2026-08-29 20:29:02.167 | 
    2026-08-29 20:29:02.167 | Error: No such command 'db-wait'.
[/FIX]

[prepare]
przeanalizuj caly projekt oraz jego logike i strukture, poszukaj bledow w przekonwertowaniu plikow na rekordy w bazie danych. 

optymalizuj projekt oraz dokonaj wewnetrznego audytu w celu poszukiwania bledow i nieprawidlowosci
[/prepare]

[prompt]
sprobuj przekonwertowac samemu plany scalone.pdf naq plik ktory pozwoli odcytac wspolrzedne etc.


http://localhost:8000/mapa?strona=1  -> dodaj mozliwosc przyblizania oddalania mapki oraz jej przeskalowanie na mniejsza skalowke. 

jesli wybiore np ten profil 

http://localhost:8000/profil/65 -> dodaj faktyczny wycinek z pdf'a  profil scalony tak aby mozna bylo potwierdzic prawdziwosc danych w apce. 

    - konwerter ma dzialac tylko jesli poprosimy o ten wycinek. dokonaj wtedy konwersji pdf i wytnij tylko interesujacy nas fragment, oraz go wyswietl lub daj 
    mozliwosc pobrania.


zaproponuj mi nowoczesne rozwiazania uzywane przy tego typu projektach oraz spytaj czy chce je dodac. 

przejdz w tryb glebokiego planowania i resarchu. 
[/prompt]

