# -*- coding: utf-8 -*-
"""Correo verificado y tokens de cuenta.

La cuenta se identifica por el correo, pero nadie confirmaba que perteneciera a
quien se registra ni había forma de recuperarla. Se añade el estado de
verificación y una tabla de tokens de un solo uso para restablecer la
contraseña y confirmar el correo, de los que solo se guarda la huella.

Revision ID: f2a7c3e91d08
Revises: e4b9c1a07d52
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f2a7c3e91d08"
down_revision: str | None = "e4b9c1a07d52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('reset','verify')", name="ck_account_tokens_purpose"
        ),
    )
    op.create_index("ix_account_tokens_hash", "account_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_account_tokens_hash", table_name="account_tokens")
    op.drop_table("account_tokens")
    # SQLite no suelta columnas sin reconstruir la tabla; el modo por lotes lo
    # hace y sobre PostgreSQL emite el ALTER de siempre.
    with op.batch_alter_table("users") as lote:
        lote.drop_column("email_verified")
