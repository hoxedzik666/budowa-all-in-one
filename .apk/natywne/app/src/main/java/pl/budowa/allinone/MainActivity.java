package pl.budowa.allinone;

import android.content.SharedPreferences;
import android.os.Bundle;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.CapConfig;

/**
 * Punkt wejscia aplikacji.
 *
 * <h2>Po co ta klasa w ogole istnieje</h2>
 *
 * Capacitor wstrzykuje most do funkcji natywnych (GPS, aparat, skaner)
 * <b>wylacznie na origin ustawiony jako {@code server.url}</b> - widac to
 * w {@code Bridge.setAllowedOriginRules()}, ktore dodaje tam wlasnie adres
 * z konfiguracji. Gdyby aplikacja ladowala lokalna strone powitalna, a potem
 * przechodzila na serwer Flaska, most przestalby istniec i zadna funkcja
 * telefonu nie bylaby wywolywalna ze stron aplikacji.
 *
 * Adres serwera nie moze byc jednak wbity przy budowaniu: przy DHCP kazda
 * zmiana IP oznaczalaby nowy APK dla calej ekipy. Musi wiec pochodzic
 * z ustawien telefonu i trafic do konfiguracji, zanim most powstanie.
 *
 * <h2>Jak to dziala</h2>
 *
 * {@code BridgeActivity.onCreate()} konczy sie wywolaniem {@code load()},
 * ktore robi {@code bridgeBuilder.setConfig(config)}. Pole {@code config}
 * jest chronione, wiec wystarczy ustawic je <b>przed</b> {@code super.onCreate()}.
 * Gdy zostawimy je puste, Capacitor wczyta {@code capacitor.config.json}
 * z zasobow - i wtedy ladujemy lokalny ekran konfiguracji adresu.
 *
 * <h2>Przy aktualizacji Capacitora sprawdz to jako pierwsze</h2>
 *
 * Capacitor nie ma publicznego API do zmiany adresu serwera w locie. Ten
 * fragment opiera sie na chronionym polu klasy bazowej, wiec przy zmianie
 * glownej wersji biblioteki trzeba go przejrzec. Opis calosci:
 * docs/project-docs/15-aplikacja-android.md
 */
public class MainActivity extends BridgeActivity {

    /** Nazwa pliku ustawien. Ten sam plik czyta wtyczka KonfiguracjaSerwera. */
    public static final String USTAWIENIA = "budowa_ustawienia";

    /** Klucz adresu serwera. Musi zgadzac sie z tym w web/shell.js. */
    public static final String KLUCZ_ADRESU = "adres_serwera";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Wtyczka do zapisu adresu musi byc znana, zanim most powstanie.
        registerPlugin(KonfiguracjaSerwera.class);

        String adres = odczytajAdres();
        if (adres != null && !adres.isEmpty()) {
            this.config = new CapConfig.Builder(this)
                .setServerUrl(adres)
                // Serwer na budowie stoi po HTTP w sieci lokalnej. Gdy pojawi
                // sie HTTPS, obie ponizsze linie mozna usunac.
                .setAndroidScheme("http")
                .setAllowMixedContent(true)
                .setAllowNavigation(new String[] { "*" })
                .create();
        }
        // Brak adresu: config zostaje pusty, Capacitor wczyta konfiguracje
        // z zasobow i pokaze lokalny ekran wpisania adresu (web/index.html).

        super.onCreate(savedInstanceState);
    }

    private String odczytajAdres() {
        SharedPreferences ustawienia = getSharedPreferences(USTAWIENIA, MODE_PRIVATE);
        String adres = ustawienia.getString(KLUCZ_ADRESU, null);
        if (adres != null) {
            return adres;
        }
        // Zapas: wtyczka @capacitor/preferences trzyma wartosci we wlasnym
        // pliku. Gdyby ekran konfiguracji zapisal adres tamtedy, i tak go
        // znajdziemy, zamiast pokazywac formularz drugi raz.
        return getSharedPreferences("CapacitorStorage", MODE_PRIVATE)
            .getString(KLUCZ_ADRESU, null);
    }

    /**
     * Przycisk wstecz cofa w historii przegladania zamiast zamykac aplikacje.
     *
     * Bez tego jedno nieuwazne dotkniecie wyrzuca brygadziste z karty odcinka
     * na pulpit telefonu - a on wlasnie stoi w wykopie i odczytuje rzedna.
     */
    @Override
    public void onBackPressed() {
        if (this.bridge != null && this.bridge.getWebView() != null
                && this.bridge.getWebView().canGoBack()) {
            this.bridge.getWebView().goBack();
            return;
        }
        super.onBackPressed();
    }
}
