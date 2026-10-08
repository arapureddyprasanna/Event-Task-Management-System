from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def blacklist_user_refresh_tokens(user, using='default'):
    outstanding_tokens = OutstandingToken.objects.using(using).filter(user=user)
    blacklist = BlacklistedToken.objects.using(using)
    for outstanding_token in outstanding_tokens.iterator():
        blacklist.get_or_create(token=outstanding_token)
