import logging
import re

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger('django')


class EmailDeliveryError(Exception):
    """Raised when an account verification email cannot be delivered."""


def _safe_error_message(exc, code):
    message = str(exc)
    secret = getattr(settings, 'EMAIL_HOST_PASSWORD', None)
    if secret:
        message = message.replace(str(secret), '[REDACTED SECRET]')
    if code:
        message = message.replace(str(code), '[REDACTED OTP]')
    message = re.sub(r'\b\d{4,8}\b', '[REDACTED OTP]', message)
    return re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        '[REDACTED EMAIL]',
        message,
    )


def send_otp_email(email, code):
    subject = 'Verify your Event & Task Management account'
    message = (
        f'Your email verification code is {code}. '
        'It expires in 10 minutes. If you did not request this, you can ignore this email.'
    )
    try:
        sent = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception as exc:
        if settings.DEBUG:
            logger.error(
                'Email delivery failed (%s): %s',
                type(exc).__name__,
                _safe_error_message(exc, code),
            )
        raise EmailDeliveryError('Verification email could not be sent.') from exc
    if sent != 1:
        raise EmailDeliveryError('Verification email could not be sent.')
