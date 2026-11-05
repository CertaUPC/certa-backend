package demo.dificiles;

/**
 * La alerta cae sobre un campo estatico, fuera de cualquier metodo.
 *
 * El recorrido del arbol sintactico no encuentra metodo contenedor, de modo
 * que el lector recorta una ventana de lineas alrededor y lo declara como
 * contexto degradado. Es el caso que hay que poder ver en pantalla.
 */
public class ConfiguracionEstatica {

    public static final String CONSULTA_BASE =
            "SELECT * FROM auditoria WHERE origen = '" + System.getenv("ORIGEN") + "'";

    public static final int TOPE = 100;

    public String describir() {
        return CONSULTA_BASE + " limite " + TOPE;
    }
}
