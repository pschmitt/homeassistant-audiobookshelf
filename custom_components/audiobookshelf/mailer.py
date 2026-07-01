"""Email sender for Send to Kindle."""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
import mimetypes
import smtplib

from homeassistant.core import HomeAssistant

from .const import (
    CONF_RECIPIENT_EMAIL,
    CONF_SENDER_EMAIL,
    CONF_SMTP_HOST,
    CONF_SMTP_PASSWORD,
    CONF_SMTP_PORT,
    CONF_SMTP_STARTTLS,
    CONF_SMTP_USERNAME,
)
from .exceptions import SendFailed
from .models import EbookFile


class KindleMailer:
    """SMTP sender for Kindle personal documents."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize the mailer."""
        self._hass = hass
        self._config = config

    async def async_send(self, ebook: EbookFile, content: bytes) -> None:
        """Send an ebook to the configured Kindle address."""
        await self._hass.async_add_executor_job(self._send, ebook, content)

    def _send(self, ebook: EbookFile, content: bytes) -> None:
        """Send an ebook synchronously in an executor."""
        message = EmailMessage()
        message["From"] = self._config[CONF_SENDER_EMAIL]
        message["To"] = self._config[CONF_RECIPIENT_EMAIL]
        message["Subject"] = ebook.display_title
        message.set_content("Sent automatically from Home Assistant via Audiobookshelf Kindle.")

        content_type, _ = mimetypes.guess_type(ebook.filename)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=ebook.filename,
        )

        try:
            with smtplib.SMTP(
                self._config[CONF_SMTP_HOST],
                int(self._config[CONF_SMTP_PORT]),
                timeout=30,
            ) as smtp:
                if self._config.get(CONF_SMTP_STARTTLS):
                    smtp.starttls()
                username = self._config.get(CONF_SMTP_USERNAME)
                password = self._config.get(CONF_SMTP_PASSWORD)
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException, asyncio.TimeoutError) as err:
            raise SendFailed(f"SMTP send failed: {err}") from err
