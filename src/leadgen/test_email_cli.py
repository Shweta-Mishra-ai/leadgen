"""Email connection test CLI.

Run this to verify your Gmail credentials and SMTP setup before sending real outreach:

    python -m leadgen.test_email_cli
    python -m leadgen.test_email_cli --to yourself@gmail.com

If credentials are missing or wrong, you will see an actionable error message.
"""
from __future__ import annotations

import argparse
import logging
import smtplib
import sys

from leadgen.config import Settings
from leadgen.email_sender import send_email

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("leadgen.test_email")


def test_smtp_connection(settings: Settings) -> bool:
    """Test raw SMTP connection and login without sending any message."""
    if not settings.gmail_address or not settings.gmail_app_password:
        logger.error(
            "❌  GMAIL_ADDRESS and GMAIL_APP_PASSWORD are not set in your .env file.\n"
            "    1. Go to https://myaccount.google.com/security\n"
            "    2. Enable 2-Step Verification\n"
            "    3. Under 'App passwords', generate a 16-character password\n"
            "    4. Add to .env:  GMAIL_ADDRESS=you@gmail.com\n"
            "                     GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx"
        )
        return False

    host = settings.smtp_host or "smtp.gmail.com"
    port = settings.smtp_port or 587
    logger.info("🔌  Connecting to %s:%s ...", host, port)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(settings.gmail_address, settings.gmail_app_password)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.gmail_address, settings.gmail_app_password)

        logger.info("✅  SMTP connection & login successful for %s", settings.gmail_address)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "❌  Authentication failed for %s.\n"
            "    — Make sure you are using a Gmail APP PASSWORD (not your normal Gmail password).\n"
            "    — Generate one at: https://myaccount.google.com/apppasswords",
            settings.gmail_address,
        )
    except smtplib.SMTPConnectError as e:
        logger.error("❌  Could not connect to SMTP server %s:%s — %s", host, port, e)
    except TimeoutError:
        logger.error("❌  Connection timed out. Check your internet connection or firewall.")
    except Exception as e:  # noqa: BLE001
        logger.error("❌  Unexpected error: %s", e)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test Gmail SMTP connection and optionally send a test email."
    )
    parser.add_argument(
        "--to",
        default=None,
        metavar="EMAIL",
        help="Send a live test email to this address (e.g. yourself@gmail.com). "
             "If omitted, only the SMTP login is tested (no email is sent).",
    )
    args = parser.parse_args()

    settings = Settings()
    logger.info("=== LeadGen Email Connection Test ===")
    logger.info("Sender identity : %s", settings.sender_name)
    logger.info("Gmail account   : %s", settings.gmail_address or "NOT SET")

    ok = test_smtp_connection(settings)
    if not ok:
        sys.exit(1)

    if args.to:
        subject = "LeadGen — Test Email ✅"
        body = (
            f"Hello,\n\n"
            f"This is a test email sent from the LeadGen outreach system.\n\n"
            f"Sender: {settings.sender_name}\n"
            f"Gmail: {settings.gmail_address}\n\n"
            f"If you received this, your email sending setup is working correctly.\n\n"
            f"Best,\n{settings.sender_name}"
        )
        logger.info("📨  Sending test email to %s ...", args.to)
        sent = send_email(settings, args.to, subject, body)
        if sent:
            logger.info("✅  Test email delivered to %s — Check your inbox!", args.to)
        else:
            logger.error("❌  Failed to send test email. Check logs above for details.")
            sys.exit(1)
    else:
        logger.info(
            "ℹ️   No --to address given. SMTP connection test only (no email sent).\n"
            "    To send a live test:  python -m leadgen.test_email_cli --to you@gmail.com"
        )


if __name__ == "__main__":
    main()
