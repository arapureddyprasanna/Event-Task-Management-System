from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_profile_registration_demo_access'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAccessRequest',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('approved', 'Approved'),
                            ('rejected', 'Rejected'),
                        ],
                        default='pending',
                        max_length=10,
                    ),
                ),
                ('decision_reason', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'requester',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='admin_access_requests',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'reviewer',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='reviewed_admin_access_requests',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={'ordering': ('-created_at', '-pk')},
        ),
        migrations.AddIndex(
            model_name='adminaccessrequest',
            index=models.Index(
                fields=['status', '-created_at'], name='acct_admreq_status_dt_idx'
            ),
        ),
        migrations.AddConstraint(
            model_name='adminaccessrequest',
            constraint=models.CheckConstraint(
                condition=models.Q(('status__in', ('pending', 'approved', 'rejected'))),
                name='accounts_admin_request_status_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='adminaccessrequest',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        models.Q(('reviewed_at__isnull', True), ('status', 'pending')),
                        models.Q(
                            ('reviewed_at__isnull', False),
                            ('status__in', ('approved', 'rejected')),
                        ),
                        _connector='OR',
                    )
                ),
                name='accounts_admin_request_reviewed_at_valid',
            ),
        ),
        migrations.AddConstraint(
            model_name='adminaccessrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'pending')),
                fields=('requester',),
                name='accounts_one_pending_admin_request',
            ),
        ),
    ]
