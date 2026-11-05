package demo.dificiles;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import javax.servlet.http.HttpServletRequest;

/**
 * El dato entra de la peticion y pasa por un saneador reconocido antes de
 * llegar al punto peligroso.
 *
 * Sirve para el caso del filtro determinista: la regla deja la senal, pero no
 * cierra el hallazgo. El veredicto lo sigue poniendo el modelo, porque un
 * saneador reconocido puede estar en una rama que el dato no toma.
 */
public class SaneadorEnElFlujo {

    private final Connection connection;

    public SaneadorEnElFlujo(Connection connection) {
        this.connection = connection;
    }

    public ResultSet buscar(HttpServletRequest request) throws Exception {
        String crudo = request.getParameter("id");
        String limpio = escapeSql(crudo);
        PreparedStatement consulta =
                connection.prepareStatement("SELECT * FROM pedidos WHERE id = '" + limpio + "'");
        return consulta.executeQuery();
    }

    private String escapeSql(String valor) {
        return valor == null ? "" : valor.replace("'", "''");
    }
}
