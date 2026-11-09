"""Additional email-MFA security checks."""
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_otp import email_is_verified
from .models import EmailVerification, SecurityEvent

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AllRolesEmailSecurityTests(TestCase):
    password = "VeryLongSecureTestPassword!2026"

    def setup_admin(self):
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password=self.password)
        EmailVerification.objects.create(user=admin, verified_email=admin.email, verified_at=timezone.now())
        return admin

    def login_admin(self):
        return self.login_with_otp("admin")

    def login_with_otp(self, username):
        response = self.client.post(reverse("accounts:login"), {
            "username": username, "password": self.password,
        })
        self.assertRedirects(response, reverse("accounts:verify_login_email"))
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)
        response = self.client.post(reverse("accounts:verify_login_email"), {"code": code})
        self.assertRedirects(response, reverse("accounts:dashboard"))
        return code

    def test_admin_cannot_open_dashboard_until_email_code_verified(self):
        self.setup_admin()
        self.client.post(reverse("accounts:login"), {"username": "admin", "password": self.password})
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 302)
        self.assertRedirects(self.client.get(reverse("admin:index")), reverse("accounts:login"))
        # Not logged in yet; pending code remains in session.
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)
        self.client.post(reverse("accounts:verify_login_email"), {"code": code})
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_staff_flagged_voter_cannot_access_admin_after_email_otp(self):
        voter = User.objects.create_user(
            username="staff-voter",
            email="staff-voter@example.com",
            password=self.password,
            is_staff=True,
        )
        EmailVerification.objects.create(
            user=voter, verified_email=voter.email, verified_at=timezone.now()
        )

        self.login_with_otp("staff-voter")

        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 403)

    def test_election_admin_can_access_admin_after_email_otp(self):
        admin = User.objects.create_user(
            username="election-admin",
            email="election-admin@example.com",
            password=self.password,
            role=User.Role.ELECTION_ADMIN,
            is_staff=True,
        )
        EmailVerification.objects.create(
            user=admin, verified_email=admin.email, verified_at=timezone.now()
        )

        self.login_with_otp("election-admin")

        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_email_change_revokes_existing_verified_session(self):
        admin = self.setup_admin()
        self.login_admin()
        admin.email = "new-admin@example.com"
        admin.save(update_fields=["email"])
        self.assertFalse(email_is_verified(admin))
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("accounts:login"))

    def test_login_code_expiration(self):
        self.setup_admin()
        self.client.post(reverse("accounts:login"), {"username": "admin", "password": self.password})
        from .models import EmailOTPChallenge
        ch = EmailOTPChallenge.objects.get(user__username="admin", purpose="LOGIN")
        ch.expires_at = timezone.now() - timedelta(seconds=1)
        ch.save(update_fields=["expires_at"])
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)
        r = self.client.post(reverse("accounts:verify_login_email"), {"code": code})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_code_audit_never_stores_otp(self):
        self.setup_admin()
        code = self.login_admin()
        self.assertTrue(SecurityEvent.objects.filter(event_type=SecurityEvent.Type.MFA_SUCCESS).exists())
        for event in SecurityEvent.objects.all():
            self.assertNotIn(code, str(event.details))

    def test_cannot_reuse_code_from_another_browser(self):
        from django.test import Client
        self.setup_admin()
        self.client.post(reverse("accounts:login"), {"username": "admin", "password": self.password})
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)
        another = Client()
        self.assertRedirects(
            another.post(reverse("accounts:verify_login_email"), {"code": code}),
            reverse("accounts:login"), fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", another.session)
