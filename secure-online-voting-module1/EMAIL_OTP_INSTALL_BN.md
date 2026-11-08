# Secure Voting System — Email OTP + Email Verification (বাংলা Setup)

## লক্ষ্য
- সব role: Voter, Election Admin, System Admin ও Authority-তে password-এর পরে email OTP।
- নতুন registration-এর পর email verification বাধ্যতামূলক। Existing admin/voter-এর email-ও প্রথম login-এ verify করতে হবে।
- OTP: ৬ ডিজিট, ৫ মিনিট, one-time, ৫টি ভুল চেষ্টা/১৫ মিনিট lock, ৬০ সেকেন্ড resend cooldown, প্রতি ঘণ্টায় ৫টি email।
- পুরোনো Authenticator-app MFA-এর routes বন্ধ করা হয়েছে। Legacy StaffMFA table মাইগ্রেশনে remove হবে। পুরোনো account, DOB, approval status মুছবে না।

## Step 1: ব্যাকআপ, ইনস্টল
Server বন্ধ করে VS Code PowerShell-এ project root `secure-online-voting-module1`-এ যাও।

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
Copy-Item .\db.sqlite3 .\db.before-email-otp.sqlite3 -Force
Copy-Item .\accounts .\accounts-before-email-otp -Recurse -Force
Copy-Item .\config .\config-before-email-otp -Recurse -Force
Copy-Item .\templates .\templates-before-email-otp -Recurse -Force
Expand-Archive -Path "$env:USERPROFILE\Downloads\Secure_Voting_Email_OTP_Module1_Update.zip" -DestinationPath . -Force
```

**ZIP-এর ভিতরে database বা .env নেই।** নতুন `config/settings.py` পুরোনো file replace করবে, তাই `DATABASE_URL`, ALLOWED_HOSTS বা custom settings থাকলে backup-এর সঙ্গে মিলিয়ে দেখো।

## Step 2: Email test — আগে Console Mode
`.env`-এ এই লাইন রাখো:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

এই mode-এ code **Django চালু থাকা terminal-এ print হবে**, inbox-এ যাবে না। Code কারও সঙ্গে share করবে না।

## Step 3: Real Email — SMTP
Inbox-এ বাস্তবে OTP পেতে `.env`-এ (শুধু example, নিজস্ব SMTP তথ্য বসাও):

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-account@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=your-account@gmail.com
```

Gmail ব্যবহারের ক্ষেত্রে account-এর 2-Step Verification ও eligible App Password প্রয়োজন হতে পারে। Normal Gmail password ব্যবহার করবে না। SMTP provider-এর নিজস্ব নির্দেশনা অনুসরণ করো। `.env` private রাখবে।

**আগে যে email দিয়ে account register করা হয়েছে সেই inbox-এ access থাকতে হবে।** Fake বা inaccessible email থাকলে প্রথমে LOCAL development environment-এ authorized admin দিয়ে email address ঠিক করো; production-এ কোনো অযাচাইকৃত email দিয়ে identity replace করবে না।

## Step 4: Django checks
```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test accounts
python manage.py runserver
```

`makemigrations --check --dry-run` existing project-এর পূর্বের migration file-গুলোর সঙ্গে model mismatch থাকলে জানাবে। কোনো error হলে migration আর এগিও না, screenshot পাঠাও।

## Step 5: Test Flow
1. `http://127.0.0.1:8000/accounts/register/` — নতুন voter register
2. Email-এ অথবা console terminal-এ VERIFY code দেখবে; ৫ মিনিটের মধ্যে submit করবে
3. Email Verified হলে login page-এ ফিরে আসবে
4. Password দিয়ে login → **নতুন LOGIN code** email-এ যাবে → verify → Dashboard
5. Voter Approved হলে আগের মতো voter dashboard; admin-only page Voter থেকে 403
6. Existing users (Admin-ও) প্রথম login-এ Verify Email → পুনরায় password → Login OTP
7. Admin verification শেষে `/admin/` ও voter review queue access পাবে

## URL
- Registration: `/accounts/register/`
- Login: `/accounts/login/`
- Email ownership code: `/accounts/email/verify/`
- Login OTP: `/accounts/email/login-code/`
- Resend: `/accounts/email/resend/` (POST only)

## Security limits
Email OTP হল email account-এর নিরাপত্তার ওপর নির্ভরশীল, phishing-resistant নয়। ভোটের মতো উচ্চ-ঝুঁকির real-world deployment-এর জন্য stronger MFA/passkey ও স্বাধীন security review দরকার।

## Error recovery
- Email না এলে: SMTP credentials, port 587/TLS ও spam folder পরীক্ষা করো; local console mode-এ terminal দেখো।
- `403 CSRF`: `CSRF` middleware সরাবে না; site-এর same-origin request, cookies ও logout form-এর `{% csrf_token %}` পরীক্ষা করো।
- `NoReverseMatch`: নিশ্চিত করো `accounts/urls.py` update হয়েছে।
- Migration failed: আগে নেওয়া backup পুনরুদ্ধার করার আগে error বুঝে নাও।
- পুরোনো login session-এ থাকলে প্রথম request-এ logout হবে; এটি security policy-এর অংশ।
