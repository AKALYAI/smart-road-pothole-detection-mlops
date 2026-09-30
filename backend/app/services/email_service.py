"""
app/services/email_service.py
---------------------------------
Best-effort email notifications (complaint status changes). If SMTP_HOST
isn't configured, the email is just printed to the console — so the whole
project still runs out of the box with zero external services, and a real
SMTP server can be plugged in later purely via environment variables.

Sends happen on a background thread so a slow/unreachable mail server
never delays the HTTP response.
"""
import smtplib
import threading
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings


def _send_now(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        print(f"[email] (no SMTP_HOST configured — printing instead)\nTo: {to_email}\nSubject: {subject}\n\n{body}\n")
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, [to_email], msg.as_string())
    except Exception as e:  # noqa: BLE001 — a failed email must never break the request
        print(f"[email] delivery to {to_email} failed: {e}")


def send_async(to_email: Optional[str], subject: str, body: str) -> None:
    if not to_email:
        return
    threading.Thread(target=_send_now, args=(to_email, subject, body), daemon=True).start()


def notify_status_change(to_email: Optional[str], complaint_id: str, new_status: str,
                          department: Optional[str] = None, note: Optional[str] = None) -> None:
    if not to_email:
        return
    subject = f"RoadWatch — complaint #{complaint_id} is now {new_status}"
    body = (
        f"Your reported pothole complaint #{complaint_id} has changed status to: {new_status}.\n"
    )
    if department:
        body += f"Assigned department: {department}\n"
    if note:
        body += f"Note: {note}\n"
    body += "\nTrack this complaint any time at the RoadWatch dashboard, Track tab.\n"
    send_async(to_email, subject, body)
