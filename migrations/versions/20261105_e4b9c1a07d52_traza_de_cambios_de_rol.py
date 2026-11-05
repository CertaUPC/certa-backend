"""Traza de los cambios de rol, lo aplicado y lo intentado

El cambio se aplicaba sin dejar rastro: el rol de una cuenta podía haber
cambiado varias veces y la tabla de cuentas solo decía el último, sin autor ni
fecha. Y un intento sin autorización no dejaba nada, de modo que no había
forma de notar que alguien lo estaba probando.

Lo encontró el grupo evaluador en el primer ciclo de pruebas cruzadas.

Revision ID: e4b9c1a07d52
Revises: c6a2f0b74d13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4b9c1a07d52"
down_revision = "c6a2f0b74d13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_changes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        # Sin clave foránea a propósito: la constancia de un intento sobre una
        # cuenta que no existe también vale.
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("from_role", sa.String(length=20), nullable=True),
        sa.Column("to_role", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_role_changes_subject", "role_changes", ["subject_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_role_changes_subject", table_name="role_changes")
    op.drop_table("role_changes")
