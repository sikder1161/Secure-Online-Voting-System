from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_voterprofile_date_of_birth"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffMFA",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("encrypted_secret", models.TextField()),
                ("enabled", models.BooleanField(default=False)),
                ("last_accepted_step", models.BigIntegerField(default=-1)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("enrolled_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                               related_name="staff_mfa", to="accounts.user")),
            ],
        ),
        migrations.CreateModel(
            name="SecurityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[
                    ("LOGIN_SUCCESS", "Login successful"), ("LOGIN_FAILURE", "Login failed"),
                    ("LOGOUT", "Logout"), ("MFA_ENROLLED", "MFA enrolled"),
                    ("MFA_FAILURE", "MFA failed"), ("MFA_SUCCESS", "MFA verified"),
                    ("ACCESS_DENIED", "Access denied"), ("VOTER_APPROVED", "Voter approved"),
                    ("VOTER_REJECTED", "Voter rejected"), ("PROFILE_UPDATED", "Profile updated"),
                    ("PASSWORD_CHANGED", "Password changed"),
                ], db_index=True, max_length=30)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True,
                                            on_delete=django.db.models.deletion.SET_NULL,
                                            related_name="security_events", to="accounts.user")),
                ("target_user", models.ForeignKey(blank=True, null=True,
                                                  on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name="targeted_security_events", to="accounts.user")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
