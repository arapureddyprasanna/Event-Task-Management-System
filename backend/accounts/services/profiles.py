from django.db import transaction

from ..models import EmailOTP, Profile
from .email import send_otp_email


@transaction.atomic
def update_user_profile(user, values):
    user = type(user).objects.select_for_update().get(pk=user.pk)
    profile = Profile.objects.select_for_update().get(user_id=user.pk)
    new_email = values.pop('email', None)

    for field, value in values.items():
        setattr(user, field, value)
    update_fields = tuple(values)
    if new_email is not None and new_email.casefold() != user.email.casefold():
        user.email = new_email
        update_fields += ('email',)
        user.save(update_fields=update_fields)
        profile.is_email_verified = False
        profile.save(update_fields=('is_email_verified', 'updated_at'))
        otp, code = EmailOTP.issue(
            user.email,
            user=user,
            purpose=EmailOTP.Purpose.VERIFY_EMAIL,
        )
        send_otp_email(otp.email, code)
    elif update_fields:
        user.save(update_fields=update_fields)
    return user
