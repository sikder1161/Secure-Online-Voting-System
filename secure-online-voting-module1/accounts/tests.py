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