# Module 1 — Secure Password Recovery + Account Activity Monitoring

এই ZIP **existing Secure Voting System project-এর update**। এটি নতুন project নয়। আগে Email OTP update এবং `accounts/migrations/0004_email_otp_and_verification.py` install করা থাকতে হবে।

## কী যোগ হবে

**Secure Password Recovery**
- `Sign in` page-এ **Forgot your password?** link।
- Verified email-এ **15-minute single-use password reset link**।
- Email unknown বা unverified হলেও একরকম response, account enumeration এড়ানোর জন্য।
- ১ ঘণ্টায় প্রতি email সর্বোচ্চ ৩টি এবং প্রতি IP সর্বোচ্চ ১০টি request (development-এর local cache; production-এ shared Redis cache দরকার)।
- Password update-এর পরে অন্য login sessions ও pending email OTP challenge invalidate হবে। Pending OTP password-hash snapshot-এর সঙ্গেও bound থাকবে, তাই password বদলালে পুরোনো OTP দিয়ে login হবে না। নতুন login-এ আবার email OTP লাগবে।
- Account activity log-এ recovery requested/completed দেখা যাবে।

**Account Activity Monitoring**
- Sidebar > **Account activity**: প্রতিটি user শুধু নিজের login, login failures, OTP failures, logout, password change/recovery, account updates দেখবে।
- Timestamp, IP এবং browser/OS summary (শুধুমাত্র request-এর REMOTE_ADDR নেওয়া হয়, untrusted `X-Forwarded-For` নয়)।
- নতুন IP/browser context হলে event record এবং verified email-এ optional alert। এই alert **device identity প্রমাণ করে না**; VPN, browser update বা network change-এর জন্যও হতে পারে।
- Admin Security Events page-এ source IP column।
- Password, reset token, OTP বা session cookie log করা হয় না।

## Installation (Windows PowerShell / VS Code)

1. Django server-এ `Ctrl + C` চাপবে। নতুন Terminal-এ:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
Test-Path .\manage.py
```
`True` হতে হবে।

2. Database ও code backup:

```powershell
Copy-Item .\db.sqlite3 .\db.backup-before-recovery.sqlite3 -Force
Copy-Item .\accounts .\accounts-backup-before-recovery -Recurse -Force
Copy-Item .\templates .\templates-backup-before-recovery -Recurse -Force
Copy-Item .\config\settings.py .\settings-backup-before-recovery.py -Force
```

3. Download করা `Secure_Voting_Password_Recovery_Account_Activity.zip` Downloads folder-এ রাখবে। Install:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\Secure_Voting_Password_Recovery_Account_Activity.zip" -DestinationPath . -Force
```

4. Check ও migration:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test accounts
```
কোনো error দেখালে থামবে। আগের SQLite database, `.env` বা user accounts এই ZIP-এ নেই।

5. Server:

```powershell
python manage.py runserver
```

## Browser demo

- Password recovery: `http://127.0.0.1:8000/accounts/password/reset/`
- Account activity: `http://127.0.0.1:8000/accounts/security/activity/`
- Admin's security overview: `http://127.0.0.1:8000/accounts/security/events/`

**Recovery test:** আগে email-verified Voter বা Admin দিয়ে reset link request করো, Gmail-এ reset email পাও, link open করে নতুন password set করো। এরপর পুরোনো password দিয়ে login fail এবং নতুন password + email OTP দিয়ে login success পরীক্ষা করো। একই reset link আবার ব্যবহার করলে invalid হতে হবে।

**Monitoring test:** নতুন browser বা Incognito দিয়ে login করে Activity page-এ success event, IP/browser info দেখো। ভুল password দিলে failed login event দেখো।

## জরুরি security note

- Password reset-এর জন্য account-এর **বর্তমান email already verified** থাকতে হবে; unverified user-কে admin-supported identity recovery দরকার।
- Django default `PasswordResetTokenGenerator` ব্যবহার হচ্ছে; password বদলালে token invalid হয়, reset timeout ১৫ মিনিট।
- Default local cache-ভিত্তিক throttle **multi-worker production-safe নয়**। Production-এর আগে shared Redis cache, HTTPS, trusted proxy configuration, `DEBUG=False`, strong `DJANGO_SECRET_KEY`, limited database/log access এবং security monitoring দরকার।
- `SecurityEvent` records এখনো cryptographically tamper-evident নয়। Module 3-এর জন্য audit-log integrity পরিকল্পনা থাকবে।
- Long-term IP retention policy থাকা উচিত। এই academic demo-তে manual retention policy implement করা হয়নি।
- `.env`, SMTP App Password, reset email link, session cookies বা OTP screenshot-এ দেখাবে না।

## User interface

Modern UI অপরিবর্তিত, শুধু Login Page-এ Forgot password link এবং Sidebar-এ Account activity যোগ হয়েছে।
