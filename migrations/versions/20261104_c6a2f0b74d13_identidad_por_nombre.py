"""El proyecto se identifica por su nombre, no por la ruta del repositorio

La ruta la escribía quien creaba el proyecto desde el navegador y no decidía
nada: quien abre los archivos es el trabajador, que corre donde el código vive
y los resuelve contra su REPOSITORY_ROOT. Peor: el cliente web la guardaba tal
cual y la línea de órdenes guardaba la absoluta ya resuelta, de modo que el
mismo repositorio acababa en dos proyectos sin que nadie lo advirtiera.

La columna se queda, porque la línea de órdenes sigue dejando ahí constancia
de sobre qué árbol corrió, pero pasa a ser anotación y no identidad. Quien
distingue dos proyectos de una misma cuenta es el nombre.

Las filas que ya existen pueden tener nombres repetidos dentro de una cuenta,
cosa que antes no estaba prohibida. Se renombran antes de crear la restricción
para que la migración no falle con datos de verdad.

Revision ID: c6a2f0b74d13
Revises: b7d3e91af204
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c6a2f0b74d13"
down_revision = "b7d3e91af204"
branch_labels = None
depends_on = None


def _desempatar_nombres() -> None:
    """Deja un solo proyecto por nombre y dueño, numerando los repetidos."""
    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text(
            "SELECT id, owner_id, name FROM projects "
            "ORDER BY owner_id, name, created_at"
        )
    ).fetchall()
    vistos: dict[tuple, int] = {}
    for fila in filas:
        clave = (fila.owner_id, fila.name)
        vistos[clave] = vistos.get(clave, 0) + 1
        if vistos[clave] == 1:
            continue
        conexion.execute(
            sa.text("UPDATE projects SET name = :nuevo WHERE id = :id"),
            {"nuevo": f"{fila.name} ({vistos[clave]})", "id": fila.id},
        )


def upgrade() -> None:
    _desempatar_nombres()
    with op.batch_alter_table("projects") as lote:
        lote.drop_constraint("uq_project_owner_path", type_="unique")
        lote.create_unique_constraint("uq_project_owner_name", ["owner_id", "name"])


def downgrade() -> None:
    with op.batch_alter_table("projects") as lote:
        lote.drop_constraint("uq_project_owner_name", type_="unique")
        lote.create_unique_constraint(
            "uq_project_owner_path", ["owner_id", "repository_path"]
        )
