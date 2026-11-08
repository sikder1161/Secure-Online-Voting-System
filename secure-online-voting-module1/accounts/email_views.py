"""Two-step password + email sign-in and email address verification.

No Django authentication session is issued until login OTP is verified.
"""
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .email_otp import (
    clear_pending, email_is_verified, issue_code, mark_login_complete,
    pending_challenge, verify_code,
)
from .models import EmailOTPChallenge, EmailVerification, SecurityEvent
from .signals import log_event


class PasswordThenEmailLoginView(auth_views.LoginView):
    """Authenticate the password, but do NOT log in until email OTP succeeds."""
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        purpose = (EmailOTPChallenge.Purpose.LOGIN if email_is_verified(user)
                   else EmailOTPChallenge.Purpose.VERIFY_EMAIL)
        # A failed email delivery never creates an authenticated session.
        result = issue_code(self.request, user, purpose)
        if result != "sent":
            messages.error(self.request, _issue_error(result))
            return redirect("accounts:login")
        next_url = self.request.POST.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            self.request.session["email_otp_next"] = next_url
        else:
            self.request.session.pop("email_otp_next", None)
        if purpose == EmailOTPChallenge.Purpose.LOGIN:
            messages.info(self.request, "A login verification code has been sent to your email.")
            return redirect("accounts:verify_login_email")
        messages.info(self.request, "Please verify your existing account email first. Then sign in again.")
        return redirect("accounts:verify_email")


def _issue_error(status):
    return {
        "cooldown": "Please wait at least 60 seconds before requesting another code.",
        "hourly_limit": "Too many emails requested. Try again in one hour.",
        "locked": "Too many attempts. Try again after 15 minutes.",
        "no_email": "This account has no email address. Contact the administrator.",
        "delivery_failed": "Could not deliver email. Check your mail configuration or try again.",
    }.get(status, "Cannot send a code right now. Sign in again.")


@never_cache
@require_http_methods(["GET", "POST"])
def verification_code(request):
    """Covers both purposes, but each URL accepts only its designated purpose."""
    intended = (EmailOTPChallenge.Purpose.LOGIN
                if request.resolver_match.url_name == "verify_login_email"
                else EmailOTPChallenge.Purpose.VERIFY_EMAIL)
    pending = pending_challenge(request)
    if not pending or pending[1] != intended:
        messages.info(request, "Start again by signing in to request a fresh code.")
        return redirect("accounts:login")
    user, purpose, challenge = pending
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        status, _, _ = verify_code(request, code)
        if status == "ok":
            clear_pending(request)
            if purpose == EmailOTPChallenge.Purpose.VERIFY_EMAIL:
                with transaction.atomic():
                    EmailVerification.objects.update_or_create(
                        user=user,
                        defaults={"verified_email": user.email, "verified_at": timezone.now()},
                    )
                log_event(SecurityEvent.Type.EMAIL_VERIFIED, actor=user, request=request)
                messages.success(request, "Email verified. Sign in with your password to receive a login code.")
                return redirect("accounts:login")
            if not email_is_verified(user):
                messages.error(request, "Email verification is required. Please sign in again.")
                return redirect("accounts:login")
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            mark_login_complete(request, user)
            log_event(SecurityEvent.Type.MFA_SUCCESS, actor=user, reason="email_otp", request=request)
            next_url = request.session.pop("email_otp_next", "")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("accounts:dashboard")
        if status in ("invalid", "locked"):
            log_event(SecurityEvent.Type.MFA_FAILURE, actor=user, reason="email_otp", request=request)
        messages.error(request, {
            "locked": "Too many incorrect codes. Try again after 15 minutes.",
            "expired": "Code expired. Request a new code after the resend cooldown.",
            "missing": "Code session no longer valid. Sign in again.",
        }.get(status, "Incorrect verification code."))
    return render(request, "accounts/email_otp.html", {
        "email": user.email,
        "purpose": purpose,
        "resend_url": reverse("accounts:resend_email_code"),
    })


@never_cache
@require_http_methods(["POST"])
def resend_email_code(request):
    pending = pending_challenge(request)
    if not pending:
        return redirect("accounts:login")
    user, purpose, _ = pending
    status = issue_code(request, user, purpose, resend=True)
    if status == "sent":
        messages.success(request, "A new code was sent. Previous codes are no longer valid.")
    else:
        messages.error(request, _issue_error(status))
    return redirect("accounts:verify_email" if purpose == "VERIFY" else "accounts:verify_login_email")
