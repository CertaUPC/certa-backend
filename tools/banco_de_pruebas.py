"""Deja el sistema listo para ejecutar los 117 casos de prueba, sin gastar.

    py tools/banco_de_pruebas.py
    py tools/banco_de_pruebas.py --puerto-proveedor 9100 --borrar

Existe por una pregunta del grupo evaluador del primer ciclo: si habia forma
de correr lo que les compartimos para que todo pase. La habia, pero repartida
en cinco herramientas y en un parrafo del manual, que es como no tenerla. Esto
las encadena.

Lo que hace, en orden:

  1. Levanta un proveedor de modelo falso en 127.0.0.1, que habla el mismo
     contrato de completado de chat que el real. Ni credencial ni saldo: lo
     unico simulado es lo que hay al otro lado del cable, y el resto es el
     codigo que correria el dia que se pague.
  2. Crea el esquema y siembra las tres cuentas, una por rol.
  3. Crea el proyecto de prueba e ingiere el SARIF de ejemplo.
  4. Valida la ejecucion entera contra el proveedor falso, de modo que las
     pantallas de revision, comparacion, exportacion y metricas tengan datos.
  5. Carga una segunda ejecucion del mismo repositorio, para que la
     comparacion tenga dos corridas que contrastar.
  6. Congela el lote del estudio y registra dos participantes, para los casos
     de la epica ocho.

Al terminar imprime lo que hace falta para empezar a pulsar: direcciones,
cuentas, identificadores y que caso del manual se puede dar con cada cosa.

No toca el despliegue. Trabaja contra la base que diga DATABASE_URL, que por
omision es el SQLite local.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from http.server import HTTPServer
from pathlib import Path
from uuid import UUID, uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# El proveedor falso vive en el ensayo de la prueba de concepto y habla el
# contrato real. Se reutiliza en vez de escribir un segundo que se desincronice.
from tools.spoc_rehearsal import Proveedor, puerto_libre

CORREOS = {
    "lider_tecnico": ("u202211399+lider@upc.edu.pe", "Certa.Lider.2026"),
    "desarrollador": ("u202211399+dev@upc.edu.pe", "Certa.Dev.2026"),
    "investigador": ("u202211399+inv@upc.edu.pe", "Certa.Inv.2026"),
}

PROYECTO = "Repositorio de ejemplo"
SARIF = RAIZ / "tools" / "demo_repo" / "vulnerable.sarif"


def _levanta_proveedor(puerto: int | None) -> tuple[HTTPServer, str]:
    puerto = puerto or puerto_libre()
    servidor = HTTPServer(("127.0.0.1", puerto), Proveedor)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return servidor, f"http://127.0.0.1:{puerto}/v1"


async def _preparar(args) -> int:
    base = _levanta_proveedor(args.puerto_proveedor)[1] if not args.sin_modelo else ""
    if base:
        # Se declaran antes de leer la configuracion: el contenedor las toma
        # al construirse y no vuelve a mirarlas.
        os.environ["LLM_BASE_URL"] = base
        os.environ["LLM_API_KEY"] = "sin-credencial-el-proveedor-es-falso"
        os.environ["LLM_MODEL"] = "banco/medio"
        os.environ["LLM_MODEL_VERSION"] = "ensayo"
    os.environ.setdefault("BUDGET_MAX_QUERIES", "500")
    # Donde el trabajador busca los archivos del SARIF. El de ejemplo los
    # nombra sueltos («UserDao.java»), de modo que la raiz es la carpeta que
    # los contiene. Sin esto no recupera contexto y no valida nada: es el
    # error que mas cuesta ver, porque la ejecucion vuelve a la cola en vez
    # de fallar.
    os.environ["REPOSITORY_ROOT"] = str(RAIZ / "tools" / "demo_repo" / "vulnerable")

    from sqlalchemy import select

    from src.iam.infrastructure.persistence.models import UserRow
    from src.iam.infrastructure.security import hash_password
    from src.shared import database_experiment as _estudio  # noqa: F401
    from src.shared.composition import Container
    from src.shared.config import get_settings
    from src.shared.database import Base, ProjectMemberRow, ProjectRow

    get_settings.cache_clear()
    settings = get_settings()
    container = Container(settings)

    async with container.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    hecho: dict[str, str] = {}

    async with container.sessions() as s:
        # --- cuentas ----------------------------------------------------
        cuentas: dict[str, str] = {}
        for rol, (correo, clave) in CORREOS.items():
            fila = (
                await s.execute(select(UserRow).where(UserRow.email == correo))
            ).scalar_one_or_none()
            if fila is None:
                fila = UserRow(
                    id=str(uuid4()), email=correo,
                    password_hash=hash_password(clave), role=rol, is_active=True,
                )
                s.add(fila)
            else:
                fila.role = rol
                fila.password_hash = hash_password(clave)
            cuentas[rol] = fila.id
        await s.commit()

        # --- proyecto ---------------------------------------------------
        proyecto = (
            await s.execute(select(ProjectRow).where(ProjectRow.name == PROYECTO))
        ).scalar_one_or_none()
        if proyecto is None:
            proyecto = ProjectRow(
                id=str(uuid4()), name=PROYECTO, language="java",
                repository_path=str(RAIZ / "tools" / "demo_repo"),
                is_public_dataset=False, owner_id=cuentas["lider_tecnico"],
            )
            s.add(proyecto)
            await s.commit()
        # Las tres cuentas dentro, para que los casos de permisos tengan a
        # quien probar sin inventar una cuarta.
        for rol, uid in cuentas.items():
            ya = (
                await s.execute(
                    select(ProjectMemberRow).where(
                        ProjectMemberRow.project_id == proyecto.id,
                        ProjectMemberRow.user_id == uid,
                    )
                )
            ).scalar_one_or_none()
            if ya is None:
                s.add(ProjectMemberRow(
                    id=str(uuid4()), project_id=proyecto.id, user_id=uid,
                    role="administrador" if rol == "lider_tecnico" else "miembro",
                ))
        await s.commit()
        hecho["proyecto"] = proyecto.id

    # --- dos ejecuciones, validadas -------------------------------------
    if not SARIF.exists():
        print(f"ERROR: no esta {SARIF}", file=sys.stderr)
        return 2
    payload = json.loads(SARIF.read_text(encoding="utf-8"))

    # Idempotente: correrlo dos veces no deja cuatro corridas. Lo contrario
    # convierte una herramienta de preparacion en una fuente de ruido.
    from src.shared.database import ExecutionRow

    ejecuciones = []
    for n in (1, 2):
        etiqueta = f"Corrida de ejemplo {n}"
        async with container.sessions() as s:
            ya = (
                await s.execute(
                    select(ExecutionRow).where(
                        ExecutionRow.project_id == hecho["proyecto"],
                        ExecutionRow.label == etiqueta,
                    )
                )
            ).scalar_one_or_none()
            if ya is not None:
                ejecuciones.append(ya.id)
                print(f"  ejecucion {n}: ya estaba, {ya.total_findings} hallazgos")
                continue
            resultado = await container.ingest_service(s).from_payload(
                UUID(hecho["proyecto"]), payload,
                created_by=UUID(cuentas["lider_tecnico"]),
                label=etiqueta,
            )
            ejecuciones.append(str(resultado.execution.id))
            print(f"  ejecucion {n}: {resultado.ingested} hallazgos")

        if base:
            async with container.sessions() as s:
                corrida = await _traer(s, UUID(ejecuciones[-1]))
                await container.runner(s, container.new_budget()).run(
                    corrida, worker="banco"
                )
            async with container.sessions() as s:
                corrida = await _traer(s, UUID(ejecuciones[-1]))
                if corrida.pending_findings:
                    print(f"  ejecucion {n}: QUEDO A MEDIAS, "
                          f"{corrida.pending_findings} sin veredicto"
                          + (f": {corrida.failure_reason}"
                             if corrida.failure_reason else ""))
                else:
                    print(f"  ejecucion {n}: validada, "
                          f"{corrida.validated_findings} veredictos")

    hecho["ejecuciones"] = ",".join(ejecuciones)

    # --- lote y participantes del estudio --------------------------------
    if base:
        from datetime import datetime, timezone

        from src.experimentation.domain.entities.participant import Participant
        from src.experimentation.infrastructure.persistence.sql_repositories import (
            SqlBatchRepository,
            SqlParticipantRepository,
        )

        async with container.sessions() as s:
            from src.shared.database import FindingRow

            hallazgos = (
                await s.execute(
                    select(FindingRow.id).where(
                        FindingRow.execution_id == ejecuciones[0]
                    )
                )
            ).scalars().all()
            mitad = max(1, len(hallazgos) // 2)
            await SqlBatchRepository(s).replace_all(
                [(h, "A" if i < mitad else "B", i)
                 for i, h in enumerate(hallazgos)]
            )
            repo = SqlParticipantRepository(s)
            for codigo in ("P-01", "P-02"):
                if await repo.get_by_code(codigo) is None:
                    await repo.save(Participant(
                        anonymous_code=codigo,
                        experience_band="de_1_a_3",
                        consented_at=datetime.now(timezone.utc),
                    ))
        print(f"  lote congelado con {len(hallazgos)} hallazgos y 2 participantes")

    await container.dispose()

    # --- lo que hace falta para empezar ----------------------------------
    print("\n" + "=" * 64)
    print("LISTO. Con esto se pueden dar los 117 casos del Manual de Pruebas.")
    print("=" * 64)
    print("\nCuentas (las tres, una por rol):")
    for rol, (correo, clave) in CORREOS.items():
        print(f"   {rol:16} {correo:32} {clave}")
    print(f"\nProyecto de prueba: {hecho['proyecto']}")
    print(f"Ejecuciones:        {hecho['ejecuciones']}")
    if base:
        print(f"Proveedor falso en: {base}")
        print("   Ya esta en el entorno de este proceso. Para el servicio y el")
        print("   trabajador, pon esas tres variables en el .env:")
        print(f"     LLM_BASE_URL={base}")
        print("     LLM_API_KEY=sin-credencial-el-proveedor-es-falso")
        print("     LLM_MODEL=banco/medio")
        print("   El proveedor falso muere con este proceso. Para dejarlo vivo,")
        print("   corre esto en una consola aparte con --servir.")
    print("\nArrancar lo demas, en dos consolas mas:")
    print("     venv\\Scripts\\python.exe -m uvicorn apps.api.main:app --reload")
    print(f"     venv\\Scripts\\python.exe -m apps.worker --proyecto {hecho['proyecto']}")
    print("   y el cliente web con npm run dev en certa-frontend.")
    print("\nQue queda cubierto:")
    print("   Epicas 1 a 3   cuentas, proyectos e ingesta, con datos ya cargados")
    print("   Epicas 4 a 6   revision, comparacion y exportacion, con dos corridas")
    print("   Epica  8       estudio, con el lote congelado y dos participantes")
    print("   Epica  7       linea de ordenes, con el repositorio de ejemplo")
    return 0


async def _traer(session, ident):
    from src.finding_validation.infrastructure.persistence.sql_repositories import (
        SqlExecutionRepository,
    )
    return await SqlExecutionRepository(session).get(ident)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="banco_de_pruebas", description=__doc__)
    p.add_argument("--puerto-proveedor", type=int, default=None,
                   help="Puerto del proveedor falso. Por omision, uno libre")
    p.add_argument("--sin-modelo", action="store_true",
                   help="No levanta el proveedor ni valida: solo cuentas, "
                        "proyecto y ejecuciones cargadas")
    p.add_argument("--servir", action="store_true",
                   help="Deja el proveedor falso escuchando hasta Ctrl+C")
    args = p.parse_args(argv)

    codigo = asyncio.run(_preparar(args))
    if codigo == 0 and args.servir and not args.sin_modelo:
        print("\nProveedor falso escuchando. Ctrl+C para parar.")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            print("\nparado")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
