"""Email-link password recovery with verified-email gating and request throttles.

Django's PasswordResetTokenGenerator binds the token to the user's password
hash and last_login; the token becomes unusable when the password changes.
"""
import hashlib
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator

from .activity_utils import client_ip
from .models import EmailOTPChallenge, EmailVerification, SecurityEvent
from .signals import log_event

logger = logging.getLogger(__name__)


class VerifiedEmailPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        """Reset only accounts whose *current* address has been verified.

        An account with an unverified email needs a separate identity-verification
        recovery process. Do not silently trust a changed account email.
        """
        for user in super().get_users(email):
            if EmailVerification.objects.filter(
                user=user, verified_at__isnull=False,
                verified_email__iexact=user.email,
            ).exists():
                yield user


def _increment_and_check(key, max_requests, window_seconds):
    # Good for a single-process local demo. Production requires a shared cache
    # such as Redis across all application workers.
    if cache.add(key, 1, timeout=window_seconds):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        count = 1
    return count > max_requests


@method_decorator(never_cache, name='dispatch')
class SecurePasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    form_class = VerifiedEmailPasswordResetForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data['email'].strip().casefold()
        # Do not persist the supplied email in a log, cache key or message.
        email_key = salted_hmac('password-recovery-email-limit-v1', email,
                                algorithm='sha256').hexdigest()
        ip_key = hashlib.sha256((client_ip(self.request) or 'unknown').encode()).hexdigest()
        limited = (
            _increment_and_check(f'pwdreset:email:{email_key}', 3, 3600)
            or _increment_and_check(f'pwdreset:ip:{ip_key}', 10, 3600)
        )
        # Same response, whether address unknown, unverified, or rate-limited.
        if limited:
            return redirect(self.get_success_url())
        for user in form.get_users(email):
            log_event(SecurityEvent.Type.PASSWORD_RESET_REQUEST, actor=user,
                      request=self.request)
        return super().form_valid(form)


@method_decorator(never_cache, name='dispatch')
class SecurePasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    post_reset_login = False  # Every role must still pass email OTP when signing in.

    def form_valid(self, form):
        # On success Django saves the password. All existing authenticated
        # sessions fail the session-auth-hash check on their next request.
        result = super().form_valid(form)
        EmailOTPChallenge.objects.filter(user=self.user).delete()
        log_event(SecurityEvent.Type.PASSWORD_RESET_DONE, actor=self.user,
                  request=self.request)
        return result
