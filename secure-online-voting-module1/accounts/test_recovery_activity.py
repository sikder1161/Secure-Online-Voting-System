"""Security regression tests for email recovery and per-user account history."""
import re
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailOTPChallenge, EmailVerification, SecurityEvent

User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SECURITY_NEW_SIGNIN_EMAIL_ALERT=False,
    PASSWORD_RESET_TIMEOUT=900,
)
class RecoveryAndActivityTests(TestCase):
    old_password = 'VeryStrongUniquePassword!2026'
    new_password = 'MyNewSecurePassword!2026'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='testvoter', email='verified@example.com', password=self.old_password
        )
        EmailVerification.objects.create(
            user=self.user, verified_email=self.user.email, verified_at=timezone.now()
        )

    def _request_reset(self, email='verified@example.com'):
        return self.client.post(reverse('accounts:password_reset'), {'email': email})

    def _extract_reset_path(self):
        text = mail.outbox[-1].body
        link = re.search(r'https?://[^\s]+', text).group(0)
        return urlsplit(link).path

    def _log_in_with_otp(self, client=None, agent='Firefox/123 (Windows)', ip='127.0.0.1'):
        client = client or self.client
        client.post(
            reverse('accounts:login'),
            {'username': self.user.username, 'password': self.old_password},
            HTTP_USER_AGENT=agent, REMOTE_ADDR=ip,
        )
        code = re.search(r'\b\d{6}\b', mail.outbox[-1].body).group(0)
        response = client.post(
            reverse('accounts:verify_login_email'), {'code': code},
            HTTP_USER_AGENT=agent, REMOTE_ADDR=ip,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', client.session)
        return client

    def test_verified_user_receives_reset_link(self):
        resp = self._request_reset()
        self.assertRedirects(resp, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/password/reset/', mail.outbox[0].body)
        self.assertTrue(SecurityEvent.objects.filter(
            actor=self.user, event_type=SecurityEvent.Type.PASSWORD_RESET_REQUEST
        ).exists())

    def test_unknown_email_has_same_response_and_no_email(self):
        a = self._request_reset('unknown@example.com')
        self.assertEqual(a.url, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_unverified_address_cannot_receive_reset_link(self):
        EmailVerification.objects.filter(user=self.user).update(verified_at=None)
        response = self._request_reset()
        self.assertEqual(response.url, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_link_is_single_use_and_old_password_invalid(self):
        self._request_reset()
        url = self._extract_reset_path()
        # Django's confirm view replaces the token in the URL with a
        # session-only sentinel before showing the change-password form.
        ready = self.client.get(url, follow=True)
        self.assertEqual(ready.status_code, 200)
        response = self.client.post(ready.redirect_chain[-1][0] if ready.redirect_chain else url, {
            'new_password1': self.new_password, 'new_password2': self.new_password,
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        replay = Client().get(url, follow=True)
        self.assertContains(replay, 'Link expired or used')
        self.assertTrue(SecurityEvent.objects.filter(
            actor=self.user, event_type=SecurityEvent.Type.PASSWORD_RESET_DONE
        ).exists())

    def test_password_change_while_otp_pending_revokes_otp(self):
        self.client.post(reverse('accounts:login'), {
            'username': self.user.username, 'password': self.old_password,
        })
        code = re.search(r'\b\d{6}\b', mail.outbox[-1].body).group(0)
        self.user.set_password(self.new_password)
        self.user.save(update_fields=['password'])
        response = self.client.post(reverse('accounts:verify_login_email'), {'code': code})
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_reset_invalidates_pending_email_otp(self):
        self.client.post(reverse('accounts:login'), {
            'username': self.user.username, 'password': self.old_password,
        })
        self.assertTrue(EmailOTPChallenge.objects.filter(user=self.user).exists())
        second = Client()
        second.post(reverse('accounts:password_reset'), {'email': self.user.email})
        path = self._extract_reset_path()
        loaded = second.get(path)
        self.assertEqual(loaded.status_code, 302)
        response = second.post(loaded.url, {
            'new_password1': self.new_password, 'new_password2': self.new_password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EmailOTPChallenge.objects.filter(user=self.user).exists())

    def test_password_reset_revokes_existing_logged_in_session(self):
        self._log_in_with_otp()
        self.assertEqual(self.client.get(reverse('accounts:dashboard')).status_code, 200)
        other = Client()
        other.post(reverse('accounts:password_reset'), {'email': self.user.email})
        path = self._extract_reset_path()
        follow = other.get(path)
        self.assertEqual(follow.status_code, 302)
        result = other.post(follow.url, {
            'new_password1': self.new_password,
            'new_password2': self.new_password,
        })
        self.assertRedirects(result, reverse('accounts:password_reset_complete'))
        self.assertRedirects(self.client.get(reverse('accounts:dashboard')),
                             reverse('accounts:login'))

    def test_recovery_requests_are_rate_limited(self):
        for _ in range(5):
            self._request_reset()
        self.assertEqual(len(mail.outbox), 3)

    def test_account_activity_requires_sign_in(self):
        self.assertRedirects(
            self.client.get(reverse('accounts:account_activity')),
            reverse('accounts:login') + '?next=' + reverse('accounts:account_activity'),
        )

    def test_activity_only_displays_current_users_events(self):
        other = User.objects.create_user(
            username='another', email='another@example.com', password=self.old_password
        )
        SecurityEvent.objects.create(
            event_type=SecurityEvent.Type.PASSWORD_CHANGED, actor=other,
            device_summary='Other confidential device'
        )
        SecurityEvent.objects.create(
            event_type=SecurityEvent.Type.LOGIN_FAILURE, target_user=self.user,
            device_summary='Own failed attempt'
        )
        self._log_in_with_otp()
        page = self.client.get(reverse('accounts:account_activity'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Own failed attempt')
        self.assertNotContains(page, 'Other confidential device')
        self.assertContains(page, 'Firefox / Windows')

    def test_new_signin_context_event_after_browser_change(self):
        self._log_in_with_otp(agent='Firefox/123 (Windows)')
        self.client.post(reverse('accounts:logout'))
        self._log_in_with_otp(agent='Chrome/145 (Windows)', ip='127.0.0.2')
        self.assertEqual(SecurityEvent.objects.filter(
            actor=self.user,
            event_type=SecurityEvent.Type.NEW_SIGNIN_CONTEXT
        ).count(), 1)

    def test_failed_login_has_ip_but_no_password(self):
        self.client.post(reverse('accounts:login'), {
            'username': self.user.username, 'password': 'WrongPasswordDontSave',
        }, REMOTE_ADDR='192.0.2.1', HTTP_USER_AGENT='Firefox/123 (Windows)')
        event = SecurityEvent.objects.get(event_type=SecurityEvent.Type.LOGIN_FAILURE)
        self.assertEqual(event.target_user, self.user)
        self.assertEqual(event.ip_address, '192.0.2.1')
        self.assertNotIn('WrongPasswordDontSave', str(event.details))

    def tearDown(self):
        cache.clear()
