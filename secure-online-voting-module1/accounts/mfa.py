"""Staff TOTP validation. No OTPs or secrets are ever written to audit logs."""
import base64
import hmac
import io
import time
from datetime import timedelta

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone


def _cipher():
    if not settings.MFA_ENCRYPTION_KEY:
        raise ImproperlyConfigured(
            "MFA_ENCRYPTION_KEY is missing. Generate it and add it to your .env."
        )
    try:
        return Fernet(settings.MFA_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("MFA_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_secret(secret):
    return _cipher().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(value):
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("ascii")
    except InvalidToken as exc:
        raise ImproperlyConfigured(
            "Unable to decrypt MFA secret. Restore the original MFA_ENCRYPTION_KEY."
        ) from exc


def provisioning_data(secret, username):
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Secure Voting System")
    qr = qrcode.QRCode(box_size=5, border=3)
    qr.add_data(uri)
    qr.make(fit=True)
    stream = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def mfa_passed(request):
    if not request.user.is_authenticated:
        return False
    from .models import StaffMFA
    return (
        request.session.get("staff_mfa_user") == request.user.pk
        and float(request.session.get("staff_mfa_expires", 0)) > time.time()
        and StaffMFA.objects.filter(user_id=request.user.pk, enabled=True).exists()
    )


def mark_mfa_verified(request):
    request.session.cycle_key()
    request.session["staff_mfa_user"] = request.user.pk
    request.session["staff_mfa_expires"] = time.time() + settings.MFA_VERIFIED_SECONDS
    request.session.modified = True


def accept_totp(mfa, code):
    """Checks 6 digits, ±1 time step, one-time use and a 5-attempt lockout.

    Uses a locked database row; production should use PostgreSQL for reliable
    concurrent update semantics. SQLite is only suitable for a local demo.
    """
    from .models import StaffMFA

    with transaction.atomic():
        record = StaffMFA.objects.select_for_update().get(pk=mfa.pk)
        now = timezone.now()
        if record.locked_until and record.locked_until > now:
            return False, "locked"
        if record.locked_until and record.locked_until <= now:
            record.failed_attempts = 0
            record.locked_until = None

        is_valid = isinstance(code, str) and len(code) == 6 and code.isascii() and code.isdecimal()
        if is_valid:
            totp = pyotp.TOTP(decrypt_secret(record.encrypted_secret))
            current_step = int(time.time()) // 30
            # Accept slight clock skew but never accept a previously used step.
            for step in (current_step - 1, current_step, current_step + 1):
                if step > record.last_accepted_step and hmac.compare_digest(
                    totp.at(step * 30), code
                ):
                    record.last_accepted_step = step
                    record.failed_attempts = 0
                    record.locked_until = None
                    record.save(update_fields=[
                        "last_accepted_step", "failed_attempts", "locked_until"
                    ])
                    return True, "ok"

        record.failed_attempts += 1
        if record.failed_attempts >= 5:
            record.locked_until = now + timedelta(minutes=15)
        record.save(update_fields=["failed_attempts", "locked_until"])
        return False, "locked" if record.locked_until else "invalid"
