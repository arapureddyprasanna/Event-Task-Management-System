from backend.accounts.models import AdminAccessRequest, Profile


def admin_request_auth_error(user):
    admin_request = user.admin_access_requests.order_by('-created_at', '-pk').first()
    if admin_request is None:
        return None
    if admin_request.status == AdminAccessRequest.Status.PENDING:
        return {
            'code': 'admin_request_pending',
            'detail': 'Admin access is pending superuser approval.',
        }
    if admin_request.status == AdminAccessRequest.Status.REJECTED:
        return {
            'code': 'admin_request_rejected',
            'detail': 'The admin access request was rejected.',
        }
    try:
        is_admin = user.is_staff and user.profile.role == Profile.Role.ADMIN
    except Profile.DoesNotExist:
        is_admin = False
    if not is_admin:
        return {
            'code': 'admin_access_not_active',
            'detail': 'Approved admin access is not active for this account.',
        }
    return None
