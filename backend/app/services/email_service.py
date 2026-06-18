"""Very small SMTP email sender.

Optional: if SMTP_* env vars are not set, functions no-op.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_enabled() -> bool:
    return bool(getattr(settings, "SMTP_HOST", None))


def send_email(to_email: str, subject: str, text: str) -> bool:
    if not _smtp_enabled():
        logger.info("SMTP not configured; skipping email to %s (%s)", to_email, subject)
        return False

    host = settings.SMTP_HOST
    port = int(getattr(settings, "SMTP_PORT", 587))
    user = getattr(settings, "SMTP_USERNAME", None)
    pw = getattr(settings, "SMTP_PASSWORD", None)
    use_tls = bool(getattr(settings, "SMTP_TLS", True))
    use_ssl = bool(getattr(settings, "SMTP_SSL", False))
    from_email = getattr(settings, "SMTP_FROM", user or "no-reply@ai-studio-pro.local")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                if user and pw:
                    s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                if use_tls:
                    s.starttls()
                if user and pw:
                    s.login(user, pw)
                s.send_message(msg)
        return True
    except Exception as e:
        logger.warning("Failed sending email: %s", e, exc_info=True)
        return False
