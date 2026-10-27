# -*- coding: utf-8 -*-
"""Separa los puntos de entrada del nucleo, en dos unidades desplegables.

Hasta ahora el servicio y el trabajador vivian dentro de `src/` y compartian
un unico requirements, de modo que no eran dos unidades sino dos formas de
arrancar la misma caja: cada PC del equipo instalaba un servidor web que no
usa, y Render instalaba tree-sitter y sus gramaticas, que no usa.

Despues de esto:

    src/                  el nucleo, intacto. Sus 201 imports relativos no se
                          tocan, porque no se mueve ningun modulo de dominio
    apps/api/             main.py           -> Render
    apps/worker/          loop.py, cli.py   -> la maquina del equipo

El CLI viaja con el trabajador porque corre en el mismo sitio y necesita lo
mismo: leer del disco, el arbol sintactico y el cliente del modelo.

Lo unico que cambia dentro de los archivos movidos son sus imports, que pasan
de relativos a absolutos contra `src`. El dominio sigue siendo uno solo, que
es lo que sostiene la prueba de la regla de dependencia y la frase del
articulo sobre compartir el codigo de dominio.

    py tools/separar_apps.py            muestra lo que haria
    py tools/separar_apps.py --aplicar  lo hace
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]

MUDANZA = [
    (RAIZ / "src/main.py", RAIZ / "apps/api/main.py"),
    (RAIZ / "src/worker.py", RAIZ / "apps/worker/loop.py"),
    (RAIZ / "src/cli.py", RAIZ / "apps/worker/cli.py"),
]

LANZADOR = '''"""Arranque del trabajador: `py -m apps.worker`."""

import asyncio
import sys

from .loop import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
'''

# ── Lo que nombra a los puntos de entrada fuera de ellos ───────────────
RETOQUES = [
    (RAIZ / "render.yaml", "uvicorn src.main:app", "uvicorn apps.api.main:app"),
    (RAIZ / "render.yaml", "`python -m src.worker`", "`python -m apps.worker`"),
    (RAIZ / "README.md", "uvicorn src.main:app", "uvicorn apps.api.main:app"),
    (RAIZ / "tests/unit/test_api.py", "from src.main import app",
     "from apps.api.main import app"),
    (RAIZ / "tests/unit/test_worker_loop.py", "from src.worker import WorkerLoop",
     "from apps.worker.loop import WorkerLoop"),
    (RAIZ / "tests/unit/test_cli_parser.py", "from src import cli",
     "from apps.worker import cli"),
    (RAIZ / "tests/arquitectura/test_schema_integrity.py",
     'ENTRADAS = ("src.cli", "src.worker", "src.main")',
     'ENTRADAS = ("apps.worker.cli", "apps.worker.loop", "apps.api.main")'),
]

# ── El reparto de dependencias ─────────────────────────────────────────
COMUNES = """# Lo que necesitan las dos unidades: el nucleo, su persistencia
# y su configuracion.
sqlalchemy[asyncio]>=2.0.36
asyncpg>=0.30.0
alembic>=1.14.0
pydantic>=2.9.0
pydantic-settings>=2.6.0
python-dotenv>=1.0.0
"""

API = """# El servicio web. No instala tree-sitter: no abre archivos de codigo.
-r ../../requirements.txt
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-jose[cryptography]>=3.3.0
bcrypt>=4.2.0
"""

WORKER = """# El trabajador y el CLI, en la maquina donde reside el codigo
# analizado. No instala servidor web: nadie le hace peticiones.
-r ../../requirements.txt
httpx>=0.27.0
tree-sitter>=0.23.0
tree-sitter-java>=0.23.0
"""


def absolutos(texto: str) -> tuple[str, int]:
    """Pasa los imports relativos del archivo movido a absolutos.

    El espacio de delante entra en el patron y vuelve a salir tal cual.
    Sin eso solo se convierten los imports que empiezan la linea, y los que
    viven dentro de una funcion se quedan relativos apuntando a un paquete
    que en el destino no existe. No se nota al importar el modulo, porque un
    import dentro de una funcion no corre hasta que alguien la llama, de modo
    que la bateria pasa entera y el arranque en despliegue revienta.
    """
    nuevo, n = re.subn(r"^(\s*)from \.(\w)", r"\1from src.\2",
                       texto, flags=re.M)
    nuevo, m = re.subn(r"^(\s*)from \. import ", r"\1from src import ",
                       nuevo, flags=re.M)
    return nuevo, n + m


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true")
    args = p.parse_args()
    hacer = args.aplicar

    print("mudanza de los puntos de entrada")
    for origen, destino in MUDANZA:
        if not origen.exists():
            print(f"  {origen.name}: ya movido, se salta")
            continue
        texto, n = absolutos(origen.read_text(encoding="utf-8"))
        print(f"  {origen.relative_to(RAIZ)} -> {destino.relative_to(RAIZ)}"
              f"   {n} imports a absolutos")
        if hacer:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
            subprocess.run(["git", "rm", "-q", "--cached", str(origen)],
                           cwd=RAIZ, capture_output=True)
            origen.unlink()

    print("\npaquetes y lanzador")
    for ruta, contenido in (
        (RAIZ / "apps/__init__.py", ""),
        (RAIZ / "apps/api/__init__.py", ""),
        (RAIZ / "apps/worker/__init__.py", ""),
        (RAIZ / "apps/worker/__main__.py", LANZADOR),
        (RAIZ / "apps/api/requirements.txt", API),
        (RAIZ / "apps/worker/requirements.txt", WORKER),
    ):
        print(f"  {ruta.relative_to(RAIZ)}")
        if hacer:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8")

    print("\nrequirements comun, sin fastapi ni tree-sitter")
    if hacer:
        (RAIZ / "requirements.txt").write_text(COMUNES, encoding="utf-8")

    print("\nreferencias a los puntos de entrada")
    for ruta, viejo, nuevo in RETOQUES:
        t = ruta.read_text(encoding="utf-8")
        if viejo not in t:
            print(f"  {ruta.relative_to(RAIZ)}: «{viejo[:44]}» NO calza")
            continue
        print(f"  {ruta.relative_to(RAIZ)}: {t.count(viejo)}x «{viejo[:44]}»")
        if hacer:
            ruta.write_text(t.replace(viejo, nuevo), encoding="utf-8")

    print("\n" + ("aplicado" if hacer else "simulacro, nada escrito"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
