from rest_framework import serializers

from .models import AdminAccessRequest


class AdminAccessRequestSerializer(serializers.ModelSerializer):
    requester = serializers.SerializerMethodField()
    reviewer = serializers.SerializerMethodField()

    class Meta:
        model = AdminAccessRequest
        fields = (
            'id', 'requester', 'status', 'reviewer', 'decision_reason',
            'created_at', 'reviewed_at',
        )
        read_only_fields = fields

    def get_requester(self, admin_request):
        user = admin_request.requester
        return {
            'id': user.pk,
            'username': user.get_username(),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    def get_reviewer(self, admin_request):
        reviewer = admin_request.reviewer
        if reviewer is None:
            return None
        return {
            'id': reviewer.pk,
            'username': reviewer.get_username(),
        }


class AdminAccessDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError({
                field: 'Unexpected field.' for field in sorted(unexpected)
            })
        return attrs
