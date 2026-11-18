"""Tokens de un solo uso para restablecer contraseña y verificar correo."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AccountTokenRow


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqlAccountTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def issue(
        self, user_id: str, purpose: str, token_hash: str, expires_at: datetime
    ) -> str:
        # Un solo token vigente por propósito: emitir uno retira los anteriores,
        # de modo que un enlace viejo deja de servir en cuanto se pide otro.
        await self._session.execute(
            update(AccountTokenRow)
            .where(
                AccountTokenRow.user_id == user_id,
                AccountTokenRow.purpose == purpose,
                AccountTokenRow.used_at.is_(None),
            )
            .values(used_at=_now())
        )
        token_id = str(uuid4())
        self._session.add(
            AccountTokenRow(
                id=token_id,
                user_id=user_id,
                purpose=purpose,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        await self._session.commit()
        return token_id

    async def claim(self, token_hash: str, purpose: str) -> str | None:
        """Devuelve el id de usuario si el token sirve, y lo marca usado.

        Nulo si no existe, ya se usó o venció: el mismo enlace no vale dos veces.
        """
        row = (
            await self._session.execute(
                select(AccountTokenRow).where(
                    AccountTokenRow.token_hash == token_hash,
                    AccountTokenRow.purpose == purpose,
                )
            )
        ).scalar_one_or_none()
        if row is None or row.used_at is not None:
            return None
        vence = row.expires_at
        if vence.tzinfo is None:
            vence = vence.replace(tzinfo=timezone.utc)
        if vence < _now():
            return None
        row.used_at = _now()
        await self._session.commit()
        return row.user_id
