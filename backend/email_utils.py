import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("qdd.email")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@quantum-drug-discovery.local")


def send_email(to_address, subject, body):
    """Send an email via SMTP if configured, otherwise log it (dev mode)."""

    if not SMTP_HOST:
        logger.info("EMAIL (dev mode, no SMTP configured) to=%s subject=%s\n%s", to_address, subject, body)
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)

    logger.info("Email sent to=%s subject=%s", to_address, subject)
