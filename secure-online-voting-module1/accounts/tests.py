"""Module 1 integration regression tests, updated for mandatory email verification."""
import re
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .email_otp import email_is_verified
from .models import EmailVerification, VoterProfile

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class Module1EmailFlowTests(TestCase):
    def setUp(self):
        self.password = "SecureAcademicTestPassword!2026"

    def registration(self, username="student1", email="student1@example.com", dob="2000-01-01"):
        return {
            "username": username,
            "first_name": "Amina", "last_name": "Rahman",
            "email": email, "institutional_id": "UNI-1001",
            "department": "CSE", "date_of_birth": dob,
            "password1": self.password, "password2": self.password,
        }

    def extract_latest_code(self):
        return re.search(r"\b\d{6}\b", mail.outbox[-1].body).group(0)

    def register_and_verify(self, dob="2000-01-01"):
        res = self.client.post(reverse("accounts:register"), self.registration(dob=dob))
        self.assertRedirects(res, reverse("accounts:verify_email"))
        user = User.objects.get(username="student1")
        self.assertFalse(email_is_verified(user))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(user.role, User.Role.VOTER)
        self.assertEqual(user.voter_profile.verification_status, "PENDING")
        self.client.post(reverse("accounts:verify_email"), {"code": self.extract_latest_code()})
        self.assertTrue(email_is_verified(user))
        return user

    def login_with_otp(self, username="student1"):
        res = self.client.post(reverse("accounts:login"), {
            "username": username, "password": self.password,
        })
        self.assertRedirects(res, reverse("accounts:verify_login_email"))
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 302)
        code = self.extract_latest_code()
        res = self.client.post(reverse("accounts:verify_login_email"), {"code": code})
        self.assertRedirects(res, reverse("accounts:dashboard"))
        return code

    def test_registration_email_proof_required_and_otp_login(self):
        user = self.register_and_verify()
        self.assertEqual(len(mail.outbox), 1)
        code = self.login_with_otp()
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 200)
        self.assertRedirects(
            self.client.post(reverse("accounts:verify_login_email"), {"code": code}),
            reverse("accounts:login"), fetch_redirect_response=False,
        )

    def test_unverified_existing_account_must_verify_before_login(self):
        User.objects.create_user(username="student1", email="student1@example.com", password=self.password)
        response = self.client.post(reverse("accounts:login"), {
            "username": "student1", "password": self.password,
        })
        self.assertRedirects(response, reverse("accounts:verify_email"))
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 302)
        self.client.post(reverse("accounts:verify_email"), {"code": self.extract_latest_code()})
        self.assertTrue(email_is_verified(User.objects.get(username="student1")))
        self.login_with_otp()

    def test_wrong_code_attempt_limit_and_hashed_otp(self):
        self.client.post(reverse("accounts:register"), self.registration())
        from .models import EmailOTPChallenge
        ch = EmailOTPChallenge.objects.get()
        self.assertNotIn(self.extract_latest_code(), ch.code_digest)
        for i in range(5):
            self.client.post(reverse("accounts:verify_email"), {"code": "000000" if self.extract_latest_code() != "000000" else "111111"})
        ch.refresh_from_db()
        self.assertIsNotNone(ch.locked_until)
        good_code = self.extract_latest_code()
        self.client.post(reverse("accounts:verify_email"), {"code": good_code})
        self.assertFalse(email_is_verified(User.objects.get(username="student1")))

    def test_resend_has_cooldown(self):
        self.client.post(reverse("accounts:register"), self.registration())
        n = len(mail.outbox)
        self.client.post(reverse("accounts:resend_email_code"))
        self.assertEqual(len(mail.outbox), n)

    def test_underage_voter_cannot_be_approved(self):
        from django.utils import timezone
        today = timezone.localdate()
        dob = date(today.year - 17, today.month, min(today.day, 28))
        voter = self.register_and_verify(dob=dob.isoformat())
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password=self.password)
        EmailVerification.objects.create(user=admin, verified_email=admin.email, verified_at=timezone.now())
        self.login_with_otp(username="admin")
        res = self.client.post(reverse("accounts:review_voter", args=[voter.voter_profile.pk]), {"decision": "APPROVED"})
        self.assertRedirects(res, reverse("accounts:voter_list"))
        voter.voter_profile.refresh_from_db()
        self.assertNotEqual(voter.voter_profile.verification_status, "APPROVED")

    def test_voter_cannot_access_staff_routes(self):
        voter = self.register_and_verify()
        self.login_with_otp()
        self.assertEqual(self.client.get(reverse("accounts:voter_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:security_dashboard")).status_code, 403)

    def test_unverified_voter_is_not_eligible_even_if_previous_admin_approved(self):
        user = User.objects.create_user(username="student1", email="student1@example.com", password=self.password)
        profile = VoterProfile.objects.create(user=user, institutional_id="UNI-1001", date_of_birth=date(2000, 1, 1), verification_status="APPROVED")
        self.assertFalse(profile.can_vote)

    def test_direct_force_login_cannot_bypass_email_otp(self):
        user = User.objects.create_user(username="student1", email="student1@example.com", password=self.password)
        from django.utils import timezone
        EmailVerification.objects.create(user=user, verified_email=user.email, verified_at=timezone.now())
        self.client.force_login(user)
        r = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(r, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_builtin_django_admin_login_does_not_bypass_email_otp(self):
        r = self.client.get(reverse("admin:login"))
        self.assertRedirects(r, reverse("accounts:login"))
        r = self.client.post(reverse("admin:login"), {"username": "admin", "password": self.password})
        self.assertRedirects(r, reverse("accounts:login"))
# FR3 - Voter Eligibility Verification Tests

class VoterEligibilityFR3Tests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="fr3_test_voter",
            email="fr3@example.com",
            password="SecureTestPassword123!"
        )

        self.profile, created = VoterProfile.objects.get_or_create(
            user=self.user,
            defaults={
                "institutional_id": "FR3-1001",
                "date_of_birth": date(2000, 1, 1),
            }
        )

        self.profile.date_of_birth = date(2000, 1, 1)
        self.profile.verification_status = "PENDING"
        self.profile.save()

    def test_18_year_age_requirement(self):
        self.assertFalse(
            self.profile.meets_age_requirement(
                date(2017, 12, 31)
            )
        )

        self.assertTrue(
            self.profile.meets_age_requirement(
                date(2018, 1, 1)
            )
        )

    def test_pending_and_rejected_voter_not_approved(self):
        self.assertFalse(self.profile.identity_approved)

        self.profile.verification_status = "REJECTED"
        self.profile.save()

        self.assertFalse(self.profile.identity_approved)

    def test_inactive_voter_not_approved(self):
        self.profile.verification_status = "APPROVED"
        self.profile.save()

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.assertFalse(self.profile.identity_approved)