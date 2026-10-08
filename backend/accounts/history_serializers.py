from rest_framework import serializers

from .models import Activity, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            'id', 'category', 'title', 'message', 'is_read',
            'related_type', 'related_id', 'created_at',
        )
        read_only_fields = fields


class ActivitySerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    target_user = serializers.SerializerMethodField()
    target_event = serializers.SerializerMethodField()
    target_task = serializers.SerializerMethodField()
    target_registration_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Activity
        fields = (
            'id', 'action_type', 'description', 'actor', 'target_user',
            'target_event', 'target_task', 'target_registration_id', 'created_at',
        )
        read_only_fields = fields

    def get_actor(self, activity):
        return self._user_summary(activity.actor)

    def get_target_user(self, activity):
        return self._user_summary(activity.target_user)

    @staticmethod
    def _user_summary(user):
        if user is None:
            return None
        return {
            'id': user.pk,
            'username': user.get_username(),
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    def get_target_event(self, activity):
        event = activity.target_event
        if event is None:
            return None
        return {'id': event.pk, 'title': event.title}

    def get_target_task(self, activity):
        task = activity.target_task
        if task is None:
            return None
        return {'id': task.pk, 'title': task.title}
