from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_emailotp_purpose_profile_is_email_verified_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='registration_demo_access',
            field=models.BooleanField(default=False),
        ),
    ]
