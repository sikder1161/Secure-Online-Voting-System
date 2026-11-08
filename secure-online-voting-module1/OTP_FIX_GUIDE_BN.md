# Secure Voting System - OTP Delivery Diagnostic Fix

This archive changes ONLY `accounts/email_otp.py`. It does not modify the database, migration files, settings, `.env`, or UI.

## Installation (Windows PowerShell)

1. Stop the Django development server (Ctrl+C).
2. Open a *new* terminal and run:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
Copy-Item .\accounts\email_otp.py .\accounts\email_otp.before-delivery-fix.py
Expand-Archive -Path "$env:USERPROFILE\Downloads\Secure_Voting_OTP_Delivery_Fix.zip" -DestinationPath . -Force
python manage.py check
python manage.py test accounts
python manage.py runserver
```

If the archive is elsewhere, use its real path instead of the assumed Downloads path.

## Test email to stored ADMIN address

Keep server running. In another terminal from the same project folder run:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; from django.core.mail import send_mail; u=get_user_model().objects.get(username='admin'); print('SMTP_ACCEPTED:', send_mail('Secure Voting System - Verify your email', 'Verification delivery diagnostic. No OTP included.', None, [u.email], fail_silently=False))"
```

- `SMTP_ACCEPTED: 1` means the SMTP backend accepted the message, NOT that it reached Inbox.
- `SMTP_ACCEPTED: 0` means the backend did not accept it.
- An exception means transport/authentication failure. Share exception *type* only, not credentials.

## Then try a NEW OTP

Return to sign-in to request a new code. The browser will now show `Could not deliver email` if send_mail returned 0 or raised. Django terminal logs a safe exception class such as `SMTPAuthenticationError` or `RuntimeError` without the OTP.

If you see a green sent banner and `SMTP_ACCEPTED: 1` but nothing in Inbox/Spam/All Mail, investigate the actual recipient, Gmail filters, sender reputation, SMTP acceptance vs downstream delivery. Never disable OTP, bypass verification or print real OTPs in logs.

## Security

Do not share `.env`, `EMAIL_HOST_PASSWORD`, `DJANGO_SECRET_KEY` or OTP screenshots. Rotate secrets if exposed. This patch is diagnostic and not a guarantee of inbox delivery.
