from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .services.tokens import blacklist_user_refresh_tokens


User = get_user_model()


@receiver(pre_save, sender=User)
def remember_auth_state(sender, instance, update_fields=None, **kwargs):
    if not instance.pk:
        instance._revoke_auth_tokens = False
        return
    if update_fields and not {'password', 'is_active'}.intersection(update_fields):
        instance._revoke_auth_tokens = False
        return
    previous = sender._base_manager.filter(pk=instance.pk).values(
        'password', 'is_active'
    ).first()
    instance._revoke_auth_tokens = bool(
        previous
        and (
            previous['password'] != instance.password
            or (previous['is_active'] and not instance.is_active)
        )
    )


@receiver(post_save, sender=User)
def revoke_tokens_after_auth_state_change(
    sender, instance, using, **kwargs
):
    if getattr(instance, '_revoke_auth_tokens', False):
        blacklist_user_refresh_tokens(instance, using=using)
    instance._revoke_auth_tokens = False
