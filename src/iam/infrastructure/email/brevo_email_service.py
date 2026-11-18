"""Adaptador de correo transaccional sobre la API HTTP de Brevo.

Se usa la API HTTP (puerto 443) en lugar de SMTP porque muchos hosts de
despliegue bloquean los puertos SMTP salientes. Si faltan la clave o el
remitente, corre en modo dev: registra el enlace y no envía, de modo que las
pruebas y el banco de pruebas nunca mandan correos reales.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_API_URL = "https://api.brevo.com/v3/smtp/email"

# Paleta de Certa para el HTML de los correos.
_INK = "#0d1117"
_INK_SOFT = "#3d4653"
_FAINT = "#8a9099"
_LINE = "#e3e6ea"
_ACCENT = "#1f6feb"
_BG = "#f4f6f8"
_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


class BrevoEmailService:
    """Envía los correos de cuenta de Certa por la API de Brevo."""

    def __init__(self, settings) -> None:
        self._api_key = settings.brevo_api_key
        self._sender_name = settings.email_sender_name
        self._sender_address = settings.email_sender_address

    def _configured(self) -> bool:
        return bool(self._api_key and self._sender_address)

    def _html(self, heading: str, body_html: str, cta_label=None, cta_link=None, note_html=None) -> str:
        cta = ""
        if cta_label and cta_link:
            cta = (
                "<table role='presentation' cellpadding='0' cellspacing='0' style='margin:22px 0 4px;'>"
                f"<tr><td style='border-radius:8px;background:{_ACCENT};'>"
                f"<a href='{cta_link}' style='display:inline-block;padding:12px 24px;color:#ffffff;"
                f"font-weight:600;font-size:15px;text-decoration:none;font-family:{_FONT};'>{cta_label}</a>"
                "</td></tr></table>"
            )
        note = ""
        if note_html:
            note = f"<p style='margin:16px 0 0;font-size:13px;line-height:1.55;color:{_FAINT};'>{note_html}</p>"
        return (
            f"<div style='margin:0;padding:24px 12px;background:{_BG};font-family:{_FONT};'>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr><td align='center'>"
            "<table role='presentation' width='480' cellpadding='0' cellspacing='0' "
            f"style='max-width:480px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid {_LINE};'>"
            f"<tr><td style='background:{_INK};padding:16px 26px;'>"
            "<span style='color:#ffffff;font-size:17px;font-weight:700;'>Certa</span>"
            "<span style='color:#9aa4b2;font-size:12px;'> · Triaje asistido de hallazgos</span>"
            "</td></tr>"
            "<tr><td style='padding:28px 26px 24px;'>"
            f"<h1 style='margin:0 0 12px;font-size:20px;line-height:1.3;color:{_INK};font-weight:700;'>{heading}</h1>"
            f"<div style='font-size:15px;line-height:1.6;color:{_INK_SOFT};'>{body_html}</div>"
            f"{cta}{note}</td></tr>"
            f"<tr><td style='padding:14px 26px;background:{_BG};border-top:1px solid {_LINE};'>"
            f"<p style='margin:0;font-size:12px;line-height:1.5;color:{_FAINT};'>"
            "Recibiste este correo porque hay una cuenta de Certa asociada a esta dirección.</p>"
            "</td></tr></table></td></tr></table></div>"
        )

    async def _send(self, to_email: str, to_name: str, subject: str, text: str, html: str) -> None:
        payload = {
            "sender": {"name": self._sender_name, "email": self._sender_address},
            "to": [{"email": to_email, "name": to_name or to_email}],
            "subject": subject,
            "htmlContent": html,
            "textContent": text,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _API_URL,
                headers={
                    "api-key": self._api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()

    async def send_password_reset(self, to_email: str, to_name: str, reset_link: str) -> None:
        if not self._configured():
            logger.info("[reset] (modo dev, sin clave) enlace para %s: %s", to_email, reset_link)
            return
        text = (
            f"Hola,\n\nRecibimos una solicitud para restablecer la contraseña de tu cuenta de Certa.\n"
            f"Abre este enlace para crear una nueva (caduca en 1 hora):\n\n{reset_link}\n\n"
            "Si no fuiste tú, ignora este correo: tu contraseña seguirá igual.\n"
        )
        html = self._html(
            "Restablece tu contraseña",
            "<p style='margin:0 0 10px;'>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>"
            "<p style='margin:0;'>El enlace <b>caduca en 1 hora</b> y solo puede usarse una vez.</p>",
            cta_label="Crear una nueva contraseña",
            cta_link=reset_link,
            note_html=(
                "Si el botón no funciona, copia este enlace:<br>"
                f"<a href='{reset_link}' style='color:{_ACCENT};word-break:break-all;'>{reset_link}</a><br><br>"
                "Si no fuiste tú, ignora este correo: tu contraseña seguirá igual."
            ),
        )
        await self._send(to_email, to_name, "Restablece tu contraseña de Certa", text, html)

    async def send_password_changed(self, to_email: str, to_name: str) -> None:
        if not self._configured():
            logger.info("[password-changed] (modo dev, sin clave) aviso para %s", to_email)
            return
        text = (
            "Hola,\n\nLa contraseña de tu cuenta de Certa acaba de cambiarse.\n"
            "Si fuiste tú, no necesitas hacer nada. Si no la reconoces, contacta al administrador.\n"
        )
        html = self._html(
            "Tu contraseña fue cambiada",
            "<p style='margin:0 0 10px;'>La contraseña de tu cuenta de Certa acaba de cambiarse correctamente.</p>"
            "<p style='margin:0;'>Si fuiste tú, no necesitas hacer nada.</p>",
            note_html="¿No reconoces este cambio? Contacta al administrador del proyecto.",
        )
        await self._send(to_email, to_name, "Tu contraseña de Certa fue cambiada", text, html)

    async def send_email_verification(self, to_email: str, to_name: str, verify_link: str) -> None:
        if not self._configured():
            logger.info("[verify] (modo dev, sin clave) enlace para %s: %s", to_email, verify_link)
            return
        text = (
            f"Hola,\n\nConfirma tu correo para activar del todo tu cuenta de Certa.\n"
            f"Abre este enlace (caduca en 24 horas):\n\n{verify_link}\n"
        )
        html = self._html(
            "Confirma tu correo",
            "<p style='margin:0 0 10px;'>Ya casi está. Confirma que esta dirección es tuya para activar del todo tu cuenta.</p>"
            "<p style='margin:0;'>El enlace <b>caduca en 24 horas</b>.</p>",
            cta_label="Confirmar mi correo",
            cta_link=verify_link,
            note_html=(
                "Si el botón no funciona, copia este enlace:<br>"
                f"<a href='{verify_link}' style='color:{_ACCENT};word-break:break-all;'>{verify_link}</a>"
            ),
        )
        await self._send(to_email, to_name, "Confirma tu correo de Certa", text, html)

    async def send_project_invitation(
        self, to_email: str, to_name: str, project_name: str, invited_by: str
    ) -> None:
        if not self._configured():
            logger.info("[invitation] (modo dev, sin clave) aviso a %s para el proyecto %s", to_email, project_name)
            return
        text = (
            f"Hola,\n\n{invited_by} te agregó al proyecto \"{project_name}\" en Certa.\n"
            "Inicia sesión con esta cuenta para verlo.\n"
        )
        html = self._html(
            "Te agregaron a un proyecto",
            f"<p style='margin:0 0 10px;'><b>{invited_by}</b> te agregó al proyecto "
            f"<b>{project_name}</b> en Certa.</p>"
            "<p style='margin:0;'>Inicia sesión con esta cuenta para verlo.</p>",
        )
        await self._send(to_email, to_name, f"Te agregaron al proyecto {project_name}", text, html)
