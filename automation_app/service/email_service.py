import resend
from django.conf import settings
import os
from dotenv import load_dotenv
import logging


logger = logging.getLogger(__name__)


def send_mail_resend(
    subject,
    message,
    recipient_list,
    fail_silently=True,
    html_message=None
):
    """
    Resend replacement for Django's send_mail
    """

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured in settings.py")

    if not settings.DEFAULT_FROM_EMAIL:
        raise RuntimeError("DEFAULT_FROM_EMAIL is not configured in settings.py")

    resend.api_key = settings.RESEND_API_KEY
    successful_sends = 0

    for email in recipient_list:
        try:
            if html_message:
                email_html = html_message
            else:
                email_html = (
                    '<div style="font-family: Arial, sans-serif; '
                    'line-height: 1.6; color: #333;">'
                    f'{message.replace(chr(10), "<br>")}'
                    '</div>'
                )

            resend.Emails.send({
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [email],
                "subject": subject,
                "html": email_html,
                "text": message,
            })

            successful_sends += 1

        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            if not fail_silently:
                raise

    return successful_sends


def send_mail(
    subject,
    message,
    recipient_list,
    fail_silently=False,
    html_message=None
):
    """
    Drop-in replacement for django.core.mail.send_mail
    """
    return send_mail_resend(
        subject,
        message,
        recipient_list,
        fail_silently,
        html_message
    )