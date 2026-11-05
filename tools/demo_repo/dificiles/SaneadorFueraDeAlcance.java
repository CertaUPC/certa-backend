package demo.dificiles;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import javax.servlet.http.HttpServletRequest;

/**
 * Aqui el saneador no esta en este archivo: vive en Saneadores.java, de modo
 * que el fragmento recuperado no lo alcanza.
 *
 * Es el caso en que el sistema tiene que declarar en la consulta que el
 * contexto esta incompleto, en vez de dejar que el modelo juzgue creyendo que
 * vio todo lo que habia que ver.
 */
public class SaneadorFueraDeAlcance {

    private final Connection connection;

    public SaneadorFueraDeAlcance(Connection connection) {
        this.connection = connection;
    }

    public ResultSet buscar(HttpServletRequest request) throws Exception {
        String valor = Saneadores.normalizar(request.getParameter("id"));
        PreparedStatement consulta =
                connection.prepareStatement("SELECT * FROM clientes WHERE id = '" + valor + "'");
        return consulta.executeQuery();
    }
}
