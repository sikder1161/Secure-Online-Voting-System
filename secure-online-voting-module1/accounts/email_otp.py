"""Email one-time codes for account email verification and password + email login.

Only a keyed digest is stored. The OTP is sent only to the user's account email.
The challenge is bound to the browser session that requested it.
"""
import hmac
import logging
import secrets
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import EmailOTPChallenge, EmailVerification

logger = logging.getLogger(__name__)


def email_is_verified(user):
    if not user.is_authenticated:
        return False
    # Query directly so a user's earlier related-object cache cannot become stale.
    return EmailVerification.objects.filter(
        user_id=user.pk,
        verified_email__iexact=user.email,
        verified_at__isnull=False,
    ).exists()


def _digest(user_pk, purpose, nonce, code):
    payload = f"{user_pk}:{purpose}:{nonce}:{code}"
    return salted_hmac("secure-vote-email-otp-v1", payload, algorithm="sha256").hexdigest()


def _session_hash(session_key):
    return salted_hmac("secure-vote-otp-session-v1", session_key, algorithm="sha256").hexdigest()


def _password_snapshot(user):
    """Invalidate pending OTP challenges if the password changes mid-flow."""
    return salted_hmac("secure-vote-password-snapshot-v1", user.password, algorithm="sha256").hexdigest()


def issue_code(request, user, purpose, *, resend=False):
    """Send challenge and set pending session state. Returns status string.

    A 60s resend cooldown, 5 messages/hour and a 15m lockout apply per user/purpose.
    An SMTP failure rolls back the code change so old valid code isn't invalidated.
    """
    if purpose not in (EmailOTPChallenge.Purpose.VERIFY_EMAIL, EmailOTPChallenge.Purpose.LOGIN):
        return "invalid"
    if not user.email:
        return "no_email"
    if resend:
        if (request.session.get("email_otp_pending_user") != user.pk or
                request.session.get("email_otp_pending_purpose") != purpose):
            return "missing"
        if not request.session.session_key:
            return "missing"
    else:
        # Prevent a session fixation attack before starting a new auth challenge.
        request.session.cycle_key()

    session_key = request.session.session_key
    now = timezone.now()
    try:
        with transaction.atomic():
            challenge, _ = EmailOTPChallenge.objects.select_for_update().get_or_create(
                user=user, purpose=purpose,
                defaults={"session_binding": "", "code_digest": "",
                          "expires_at": now, "hour_started_at": now},
            )
            if challenge.locked_until and challenge.locked_until > now:
                return "locked"
            if challenge.locked_until and challenge.locked_until <= now:
                challenge.locked_until = None
                challenge.failed_attempts = 0
            if challenge.last_sent_at and now - challenge.last_sent_at < timedelta(seconds=60):
                return "cooldown"
            if now - challenge.hour_started_at >= timedelta(hours=1):
                challenge.hour_started_at = now
                challenge.sent_in_hour = 0
            if challenge.sent_in_hour >= 5:
                return "hourly_limit"

            code = f"{secrets.randbelow(1_000_000):06d}"
            nonce = uuid.uuid4().hex
            challenge.nonce = nonce
            challenge.code_digest = _digest(user.pk, purpose, nonce, code)
            challenge.session_binding = _session_hash(session_key)
            challenge.expires_at = now + timedelta(minutes=5)
            challenge.last_sent_at = now
            challenge.sent_in_hour += 1
            # Do not reset failed_attempts on resend: otherwise it bypasses lockout.
            challenge.save()

            if purpose == EmailOTPChallenge.Purpose.VERIFY_EMAIL:
                subject = "Secure Voting System - Verify your email"
                intent = "verify your email address"
            else:
                subject = "Secure Voting System - Login verification code"
                intent = "complete your login"
            sent_count = send_mail(
                subject,
                f"Your verification code to {intent} is: {code}\n\n"
                "This code expires in 5 minutes. Do not share it with anyone.\n"
                "If you did not request this code, ignore this email.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            # A backend may return 0 without raising an exception. Never show
            # the user a false 'code sent' confirmation in that case.
            if sent_count != 1:
                raise RuntimeError("Email backend did not accept the OTP message")
    except Exception as exc:
        # Never log the code, SMTP credentials, recipient address or exception
        # message: SMTP errors can include sensitive transport information.
        logger.warning("OTP sending failed (%s)", type(exc).__name__)
        return "delivery_failed"

    request.session["email_otp_pending_user"] = user.pk
    request.session["email_otp_pending_purpose"] = purpose
    request.session["email_otp_pending_email"] = user.email
    request.session["email_otp_pending_password"] = _password_snapshot(user)
    request.session.modified = True
    return "sent"


def pending_challenge(request):
    """Return (user, purpose, challenge) only for the issuing session."""
    from django.contrib.auth import get_user_model

    user_id = request.session.get("email_otp_pending_user")
    purpose = request.session.get("email_otp_pending_purpose")
    current_email = request.session.get("email_otp_pending_email")
    if not user_id or purpose not in ("VERIFY", "LOGIN"):
        return None
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if not user or not user.email or user.email != current_email:
        return None
    snapshot = request.session.get("email_otp_pending_password", "")
    if not snapshot or not hmac.compare_digest(snapshot, _password_snapshot(user)):
        return None
    challenge = EmailOTPChallenge.objects.filter(user=user, purpose=purpose).first()
    if (not challenge or not request.session.session_key or
            not hmac.compare_digest(challenge.session_binding, _session_hash(request.session.session_key))):
        return None
    return user, purpose, challenge


def verify_code(request, code):
    """Consume code with an atomic check, return (status, user, purpose).

    PostgreSQL row locks provide concurrency safety; SQLite remains demo-only.
    """
    pending = pending_challenge(request)
    if pending is None:
        return "missing", None, None
    user, purpose, current = pending
    with transaction.atomic():
        challenge = EmailOTPChallenge.objects.select_for_update().get(pk=current.pk)
        now = timezone.now()
        if challenge.locked_until and now < challenge.locked_until:
            return "locked", user, purpose
        if challenge.locked_until and now >= challenge.locked_until:
            challenge.locked_until = None
            challenge.failed_attempts = 0
            challenge.save(update_fields=["locked_until", "failed_attempts"])
        if now > challenge.expires_at:
            return "expired", user, purpose
        if (isinstance(code, str) and len(code) == 6 and code.isascii() and code.isdecimal() and
                hmac.compare_digest(challenge.code_digest,
                                    _digest(user.pk, purpose, challenge.nonce, code))):
            challenge.delete()  # Enforce single-use code.
            return "ok", user, purpose
        challenge.failed_attempts += 1
        if challenge.failed_attempts >= 5:
            challenge.locked_until = now + timedelta(minutes=15)
        challenge.save(update_fields=["failed_attempts", "locked_until"])
        return ("locked" if challenge.locked_until else "invalid"), user, purpose


def clear_pending(request):
    for key in ("email_otp_pending_user", "email_otp_pending_purpose", "email_otp_pending_email", "email_otp_pending_password"):
        request.session.pop(key, None)


def mark_login_complete(request, user):
    """Call only after successful email OTP + Django login."""
    request.session["email_otp_auth_user"] = user.pk
    request.session["email_otp_auth_email"] = user.email
    request.session["email_otp_auth_until"] = time.time() + settings.EMAIL_MFA_SESSION_SECONDS
    request.session.modified = True


def email_login_passed(request):
    user = request.user
    return bool(
        user.is_authenticated
        and request.session.get("email_otp_auth_user") == user.pk
        and request.session.get("email_otp_auth_email") == user.email
        and float(request.session.get("email_otp_auth_until", 0)) > time.time()
        and email_is_verified(user)
    )
