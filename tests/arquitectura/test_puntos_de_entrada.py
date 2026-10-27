"""Los imports de las unidades desplegables apuntan a algo que existe.

Al separar el servicio y el trabajador en `apps/`, sus imports relativos
tuvieron que pasar a absolutos contra `src`, porque el dominio se quedo donde
estaba. La herramienta que hizo la mudanza convirtio los que empezaban la
linea y se dejo tres que vivian dentro de una funcion: dos en el sembrado del
primer administrador y uno en la consulta de tarifas del comando `compare`.

Ninguna prueba los vio. Un import dentro de una funcion no se ejecuta al
importar el modulo, de modo que la bateria pasaba entera mientras el arranque
del servicio en despliegue reventaba con `No module named apps.api.iam`.

De ahi la regla: dentro de `apps/` un import relativo solo vale si el modulo
que nombra existe como hermano en ese mismo paquete. El lanzador del
trabajador cumple, porque `loop.py` esta a su lado. Cualquier otro es un resto
de la mudanza, y la prueba lo nombra con su archivo y su linea en vez de
esperar a que alguien despliegue.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"

MODULOS = sorted(p for p in APPS.rglob("*.py") if p.stat().st_size > 0)


def _paquete(archivo: pathlib.Path, nivel: int) -> pathlib.Path:
    """La carpeta a la que resuelve un import de `nivel` puntos."""
    carpeta = archivo.parent
    for _ in range(nivel - 1):
        carpeta = carpeta.parent
    return carpeta


def test_hay_modulos_que_revisar() -> None:
    """Si la mudanza se deshace, que no pase por vacio."""
    assert MODULOS, "no hay nada bajo apps/, la prueba no esta comprobando nada"


@pytest.mark.parametrize("archivo", MODULOS, ids=lambda p: p.name)
def test_los_relativos_nombran_a_un_hermano_real(archivo: pathlib.Path) -> None:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    sueltos = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ImportFrom) or not nodo.level:
            continue
        carpeta = _paquete(archivo, nodo.level)
        cabeza = (nodo.module or "").split(".")[0]
        existe = (carpeta / f"{cabeza}.py").exists() or (
            carpeta / cabeza / "__init__.py"
        ).exists()
        if not existe:
            puntos = "." * nodo.level
            sueltos.append(f"    linea {nodo.lineno}: from {puntos}{nodo.module}")

    assert not sueltos, (
        f"{archivo.name} importa en relativo algo que no esta a su lado.\n"
        + "\n".join(sueltos)
        + "\n    El dominio vive en src/, de modo que el import va absoluto: "
        "from src.<lo que sea>"
    )
