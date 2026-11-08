from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_email_otp_and_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='securityevent',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='securityevent',
            name='device_summary',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='securityevent',
            name='context_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name='securityevent',
            name='event_type',
            field=models.CharField(
                db_index=True,
                max_length=30,
                choices=[
                    ('EMAIL_CODE_SENT', 'Email verification code sent'),
                    ('EMAIL_VERIFIED', 'Email verified'),
                    ('LOGIN_SUCCESS', 'Login successful'),
                    ('LOGIN_FAILURE', 'Login failed'),
                    ('LOGOUT', 'Logout'),
                    ('MFA_ENROLLED', 'MFA enrolled'),
                    ('MFA_FAILURE', 'MFA failed'),
                    ('MFA_SUCCESS', 'MFA verified'),
                    ('ACCESS_DENIED', 'Access denied'),
                    ('VOTER_APPROVED', 'Voter approved'),
                    ('VOTER_REJECTED', 'Voter rejected'),
                    ('PROFILE_UPDATED', 'Profile updated'),
                    ('PASSWORD_CHANGED', 'Password changed'),
                    ('PASSWORD_RESET_REQ', 'Password recovery requested'),
                    ('PASSWORD_RESET_DONE', 'Password recovered'),
                    ('NEW_SIGNIN_CONTEXT', 'New sign-in context'),
                ],
            ),
        ),
    ]
