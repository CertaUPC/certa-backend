package demo.dificiles;

/** El saneador que SaneadorFueraDeAlcance usa y su fragmento no alcanza. */
public final class Saneadores {

    private Saneadores() {
    }

    public static String normalizar(String valor) {
        if (valor == null) {
            return "";
        }
        return valor.replaceAll("[^A-Za-z0-9_-]", "");
    }
}
