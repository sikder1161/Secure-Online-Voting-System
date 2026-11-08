from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_staffmfa_securityevent")]

    operations = [
        migrations.DeleteModel(name="StaffMFA"),
        migrations.CreateModel(
            name="EmailVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("verified_email", models.EmailField(blank=True, max_length=254)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                               related_name="email_verification", to="accounts.user")),
            ],
        ),
        migrations.CreateModel(
            name="EmailOTPChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(choices=[("VERIFY", "Email ownership verification"),
                                                      ("LOGIN", "Sign-in verification")], max_length=10)),
                ("nonce", models.CharField(blank=True, max_length=32)),
                ("code_digest", models.CharField(blank=True, max_length=64)),
                ("session_binding", models.CharField(blank=True, max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("sent_in_hour", models.PositiveSmallIntegerField(default=0)),
                ("hour_started_at", models.DateTimeField()),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="email_challenges", to="accounts.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="emailotpchallenge",
            constraint=models.UniqueConstraint(fields=("user", "purpose"), name="one_email_challenge_per_purpose"),
        ),
        migrations.AlterField(
            model_name="securityevent", name="event_type",
            field=models.CharField(max_length=30, db_index=True, choices=[
                ("EMAIL_CODE_SENT", "Email verification code sent"),
                ("EMAIL_VERIFIED", "Email verified"),
                ("LOGIN_SUCCESS", "Login successful"),
                ("LOGIN_FAILURE", "Login failed"),
                ("LOGOUT", "Logout"),
                ("MFA_ENROLLED", "MFA enrolled"),
                ("MFA_FAILURE", "MFA failed"),
                ("MFA_SUCCESS", "MFA verified"),
                ("ACCESS_DENIED", "Access denied"),
                ("VOTER_APPROVED", "Voter approved"),
                ("VOTER_REJECTED", "Voter rejected"),
                ("PROFILE_UPDATED", "Profile updated"),
                ("PASSWORD_CHANGED", "Password changed"),
            ]),
        ),
    ]
