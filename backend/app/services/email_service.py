import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import Optional
from app.config import settings


def send_email_with_attachments(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    if settings.resend_api_key:
        return _send_via_resend(to, subject, body, attachments)
    if settings.smtp_host:
        return _send_via_smtp(to, subject, body, attachments)
    return False


def _send_via_resend(to: str, subject: str, body: str, attachments) -> bool:
    try:
        import resend
        resend.api_key = settings.resend_api_key
        params: dict = {
            "from": f"Pôle Emploi Assistant <noreply@{settings.smtp_user or 'assistant.pole-emploi.fr'}>",
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if attachments:
            params["attachments"] = [
                {"filename": name, "content": list(content)} for name, content in attachments
            ]
        resend.Emails.send(params)
        return True
    except Exception:
        return False


def _send_via_smtp(to: str, subject: str, body: str, attachments) -> bool:
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachments:
            for filename, content in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, to, msg.as_string())
        return True
    except Exception:
        return False
