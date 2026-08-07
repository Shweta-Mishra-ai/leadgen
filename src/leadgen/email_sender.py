from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from leadgen.config import Settings

logger = logging.getLogger("leadgen.email_sender")


def send_email(
    settings: Settings,
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> bool:
    """Sends a direct email via Gmail / SMTP server using settings configuration.

    Returns True if sent successfully, False otherwise.
    """
    if not settings.gmail_address or not settings.gmail_app_password:
        logger.warning("Gmail credentials (GMAIL_ADDRESS & GMAIL_APP_PASSWORD) missing.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{settings.sender_name} <{settings.gmail_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, mime_type, "utf-8"))

        host = settings.smtp_host or "smtp.gmail.com"
        port = settings.smtp_port or 587

        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                server.login(settings.gmail_address, settings.gmail_app_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls()
                server.login(settings.gmail_address, settings.gmail_app_password)
                server.send_message(msg)

        logger.info("Email sent successfully to %s: %r", to_email, subject)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False
