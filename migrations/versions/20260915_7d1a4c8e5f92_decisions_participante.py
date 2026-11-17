# -*- coding: utf-8 -*-
"""Declara en el motor la referencia de decisions a participants.

La columna existia y guardaba el identificador del participante, pero como
cadena suelta: la integridad quedaba a cargo de la aplicacion. Dentro del mismo
esquema, sessions.participant_id si declaraba la clave foranea, de modo que la
misma relacion estaba resuelta de dos maneras.

Importa donde esta: decisions guarda la variable dependiente principal del
experimento. Una decision cuyo participante ya no existe no es un dato
incompleto, es un resultado que no se puede defender.

No aplica aqui la frontera entre contextos delimitados que justifica dejar
finding_id como identidad: participants y decisions viven los dos en el
contexto de experimentacion.

El borrado en cascada es deliberado y responde al consentimiento informado: si
un participante se retira y se le borra, sus decisiones se van con el.

Revision ID: 7d1a4c8e5f92
Revises: 4b2e91a7c3d8
"""
from __future__ import annotations

from alembic import op

revision: str = "7d1a4c8e5f92"
down_revision: str | None = "4b2e91a7c3d8"
branch_labels = None
depends_on = None

RESTRICCION = "fk_decisions_participant"


def upgrade() -> None:
    # Las filas huerfanas impedirian crear la restriccion, y son justamente lo
    # que esta migracion existe para volver imposible. Se retiran primero: una
    # decision sin participante no se puede atribuir a nadie y no entra en
    # ningun analisis.
    op.execute(
        "DELETE FROM decisions WHERE participant_id NOT IN "
        "(SELECT id FROM participants)"
    )
    # En lote y no con ALTER directo: en desarrollo la base es SQLite, que no
    # admite anadir una restriccion a una tabla existente. El modo por lotes la
    # reconstruye; sobre PostgreSQL emite el ALTER de siempre.
    with op.batch_alter_table("decisions") as lote:
        lote.create_foreign_key(
            RESTRICCION,
            referent_table="participants",
            local_cols=["participant_id"],
            remote_cols=["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # SQLite no guarda el nombre de la clave foranea, de modo que al reflejar la
    # tabla el modo por lotes no la encuentra para soltarla y el downgrade cae.
    # Se le pasa una convencion de nombres: con ella la restriccion reflejada
    # recibe un nombre por el que si se puede referir. Sobre PostgreSQL, donde el
    # nombre si persiste, se emite el ALTER directo con el nombre original.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        convencion = {
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }
        with op.batch_alter_table(
            "decisions", naming_convention=convencion
        ) as lote:
            lote.drop_constraint(
                "fk_decisions_participant_id_participants", type_="foreignkey"
            )
    else:
        op.drop_constraint(RESTRICCION, "decisions", type_="foreignkey")
