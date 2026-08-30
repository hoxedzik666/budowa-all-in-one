package pl.budowa.allinone;

import android.content.Intent;
import android.content.SharedPreferences;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Zapis adresu serwera i ponowne uruchomienie aplikacji.
 *
 * Ekran konfiguracji (web/shell.js) wola {@code ustaw({adres})}. Sam zapis
 * nie wystarczy: adres trafia do konfiguracji Capacitora dopiero przy tworzeniu
 * mostu, czyli w {@link MainActivity#onCreate}. Dlatego po zapisaniu
 * uruchamiamy aktywnosc od nowa - i tym razem laduje sie juz serwer Flaska,
 * z dzialajacymi GPS-em, aparatem i skanerem.
 */
@CapacitorPlugin(name = "KonfiguracjaSerwera")
public class KonfiguracjaSerwera extends Plugin {

    @PluginMethod
    public void ustaw(PluginCall wywolanie) {
        String adres = wywolanie.getString("adres");
        if (adres == null || adres.trim().isEmpty()) {
            wywolanie.reject("Adres serwera jest pusty.");
            return;
        }

        zapisz(adres.trim());
        wywolanie.resolve();
        uruchomPonownie();
    }

    @PluginMethod
    public void pobierz(PluginCall wywolanie) {
        JSObject wynik = new JSObject();
        wynik.put("adres", ustawienia().getString(MainActivity.KLUCZ_ADRESU, ""));
        wywolanie.resolve(wynik);
    }

    /**
     * Zapomnij adres i wroc do ekranu konfiguracji.
     *
     * Potrzebne, gdy serwer dostanie inny adres IP albo ekipa przenosi sie
     * na inna budowe - inaczej trzeba by odinstalowac aplikacje.
     */
    @PluginMethod
    public void zapomnij(PluginCall wywolanie) {
        ustawienia().edit().remove(MainActivity.KLUCZ_ADRESU).apply();
        wywolanie.resolve();
        uruchomPonownie();
    }

    private SharedPreferences ustawienia() {
        return getContext().getSharedPreferences(MainActivity.USTAWIENIA,
                                                 android.content.Context.MODE_PRIVATE);
    }

    private void zapisz(String adres) {
        ustawienia().edit().putString(MainActivity.KLUCZ_ADRESU, adres).apply();
    }

    private void uruchomPonownie() {
        // Pelny restart aktywnosci z wyczyszczeniem stosu. Zwykle
        // `recreate()` nie wystarczy: most Capacitora powstaje raz i trzyma
        // adres, z ktorym sie urodzil.
        Intent zamiar = new Intent(getContext(), MainActivity.class);
        zamiar.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        getContext().startActivity(zamiar);
        if (getActivity() != null) {
            getActivity().finish();
        }
    }
}
