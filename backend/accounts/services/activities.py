from backend.accounts.models import Activity


def create_activity(
    actor,
    action_type,
    description,
    *,
    target_user=None,
    target_event=None,
    target_task=None,
    target_registration=None,
):
    return Activity.objects.create(
        actor=actor,
        action_type=action_type,
        description=description,
        target_user=target_user,
        target_event=target_event,
        target_task=target_task,
        target_registration=target_registration,
    )
