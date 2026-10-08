from backend.accounts.models import Notification


def create_notification(
    recipient,
    category,
    title,
    message,
    *,
    related_type='',
    related_id=None,
):
    return Notification.objects.create(
        recipient=recipient,
        category=category,
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
    )
