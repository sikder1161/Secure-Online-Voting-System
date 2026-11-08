"""Authentication audit trail, including IP and sign-in context (never secrets)."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.mail import send_mail
from django.dispatch import receiver
from django.utils import timezone

from .activity_utils import client_device, client_ip
from .models import SecurityEvent

logger = logging.getLogger(__name__)


def log_event(kind, actor=None, target_id=None, request=None, **details):
    # Explicit allowlist, never OTP, password, reset token, session cookie, or ballot data.
    allowed = {key: str(value)[:96] for key, value in details.items()
               if key in {'username', 'reason', 'action'}}
    device, context_hash = client_device(request)
    return SecurityEvent.objects.create(
        event_type=kind,
        actor=actor if actor and actor.is_authenticated else None,
        target_user_id=target_id,
        details=allowed,
        ip_address=client_ip(request),
        device_summary=device if request else '',
        context_hash=context_hash,
    )


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    _, fingerprint = client_device(request)
    prior_logins = SecurityEvent.objects.filter(
        event_type=SecurityEvent.Type.LOGIN_SUCCESS,
        actor=user,
    )
    has_previous = prior_logins.exists()
    unrecognized = has_previous and fingerprint and not prior_logins.filter(context_hash=fingerprint).exists()
    log_event(SecurityEvent.Type.LOGIN_SUCCESS, actor=user, request=request)
    if not unrecognized:
        return
    log_event(SecurityEvent.Type.NEW_SIGNIN_CONTEXT, actor=user, request=request)
    # Notification failure does not lock users out of their own accounts.
    if not getattr(settings, 'SECURITY_NEW_SIGNIN_EMAIL_ALERT', True):
        return
    try:
        from .email_otp import email_is_verified
        if not email_is_verified(user):
            return
        device, _ = client_device(request)
        send_mail(
            'Secure Voting System - New sign-in context',
            f'A new sign-in context was observed on your account.\n'
            f'When: {timezone.localtime(timezone.now()):%Y-%m-%d %H:%M %Z}\n'
            f'Browser/OS: {device}\n'
            'If this was not you, reset your password promptly.\n'
            'This alert is informational and may also occur after network or browser changes.',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning('New sign-in alert delivery failed (%s)', type(exc).__name__)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    log_event(SecurityEvent.Type.LOGOUT, actor=user, request=request)


@receiver(user_login_failed)
def on_login_failure(sender, credentials, request, **kwargs):
    username = str(credentials.get('username', ''))[:96]
    matched = (get_user_model().objects.filter(username__iexact=username)
               .values_list('id', flat=True).first()) if username else None
    log_event(SecurityEvent.Type.LOGIN_FAILURE, request=request, target_id=matched,
              username=username)
