"""Puerto de notificación por correo.

El dominio nombra lo que hay que comunicar, no cómo se envía. El adaptador
concreto (Brevo) vive en infraestructura, y en pruebas se sustituye por uno
falso que captura lo enviado sin salir a la red.
"""

from typing import Protocol


class EmailService(Protocol):
    async def send_password_reset(
        self, to_email: str, to_name: str, reset_link: str
    ) -> None: ...

    async def send_password_changed(self, to_email: str, to_name: str) -> None: ...

    async def send_email_verification(
        self, to_email: str, to_name: str, verify_link: str
    ) -> None: ...

    async def send_project_invitation(
        self, to_email: str, to_name: str, project_name: str, invited_by: str
    ) -> None: ...
