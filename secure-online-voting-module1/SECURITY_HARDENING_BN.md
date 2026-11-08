# Secure Voting System - Module 1 Security Hardening (Bangla Guide)

এই ZIP তোমার **বর্তমান Module 1** (DOB + Modern UI) project-এর ওপর update হিসেবে বসবে। এখানে `db.sqlite3`, `.env`, uploaded voter data বা existing migration 0001/0002 নেই। Update-এর আগে backup অবশ্যই রাখবে।

## 1) VS Code-এ backup ও install

**Django server বন্ধ:** server চলা Terminal-এ `Ctrl + C` চাপো।

PowerShell terminal-এ প্রতিটি command আলাদা করে চালাও:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
Copy-Item .\db.sqlite3 .\db.backup-before-security.sqlite3 -ErrorAction SilentlyContinue
Copy-Item .\accounts .\accounts-backup-before-security -Recurse -Force
Copy-Item .\templates .\templates-backup-before-security -Recurse -Force
Copy-Item .\config\settings.py .\settings-backup-before-security.py -Force
Expand-Archive -Path "$env:USERPROFILE\Downloads\secure-voting-module1-security-hardening.zip" -DestinationPath . -Force
..\venv\Scripts\python.exe -m pip install -r requirements.txt
```

ZIP অন্য folder-এ download হলে `Expand-Archive -Path`-এ সেই path বসাবে। ZIP manually extract করলে project folder-এ `accounts/`, `config/`, `templates/`, `requirements.txt` সরাসরি merge করবে; কোনো extra parent folder রাখবে না।

## 2) MFA secret encryption key একবারই তৈরি করো

**এই key হারালে পুরোনো authenticator secrets decrypt করা যাবে না।** Key কাউকে দেবে না, screenshot-এ দেখাবে না, GitHub-এ upload করবে না।

নিচের command `cryptography` install হওয়ার **পরে** চালাবে। `.env`-এ আগে থেকে MFA key থাকলে আবার চালাবে না:

```powershell
..\venv\Scripts\python.exe -c "from pathlib import Path; from cryptography.fernet import Fernet; p=Path('.env'); s=p.read_text(encoding='utf-8'); assert 'MFA_ENCRYPTION_KEY=' not in s, 'MFA key already exists!'; p.write_text(s.rstrip()+'\nMFA_ENCRYPTION_KEY='+Fernet.generate_key().decode()+'\n', encoding='utf-8'); print('MFA key saved securely to .env')"
```

`.env` ইতিমধ্যে `.gitignore`-এ থাকা উচিত। **Key rotation** কখনো শুধু `.env` value বদলে করবে না; বিদ্যমান secret decrypt করতে পুরোনো key লাগে।

## 3) Database migration এবং automated test

```powershell
..\venv\Scripts\python.exe manage.py check
..\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py test accounts
..\venv\Scripts\python.exe manage.py findstatic css/voting-modern.css
..\venv\Scripts\python.exe manage.py runserver
```

`No changes detected`, `Applying accounts.0003... OK` ও `OK` test report আশা করা যায়। **টেস্টে failure হলে server deploy করবে না; error-এর screenshot/code পাঠাবে।**

## 4) Admin 2FA setup (প্রথমবার)

1. Browser-এ `http://127.0.0.1:8000/accounts/login/` খুলো এবং `admin` দিয়ে login করো।
2. Security upgrade-এর কারণে admin dashboard-এর আগে `/accounts/mfa/setup/`-এ পাঠাবে।
3. বর্তমান admin password আবার enter করো (এবার browser input-এ `••••` দেখা যাবে)।
4. Phone-এর Google Authenticator / Microsoft Authenticator / compatible TOTP app দিয়ে QR scan করো। QR code **কাউকে পাঠাবে না**।
5. App-এর ৬-digit code enter করো; যাচাই successful হলে dashboard খুলবে।
6. পরবর্তী login-এ password-এর পাশাপাশি authenticator code দিতে হবে। একই code দ্বিতীয়বার গ্রহণ করা হবে না; 30 seconds পরে নতুন code ব্যবহার করো।

**Admin account-এর 2FA হারালে:** Admin-এর OS/server console access থাকা trusted administrator audit trail দেখে supervised MFA reset করবে। কোনো public recovery/bypass link নেই। Demo-only CLI recovery: `python manage.py shell -c "from accounts.models import StaffMFA; StaffMFA.objects.filter(user__username='admin').delete()"`। এটি কাউকে publicly expose করবে না। Production-এ supervised dual-control recovery procedure প্রয়োজন।

## 5) Security Dashboard

Admin 2FA verification-এর পরে sidebar-এ **Security events** দেখা যাবে। Direct: `http://127.0.0.1:8000/accounts/security/events/`।

Live logs-এ failed login, login/logout, MFA attempts, denied staff access, profile change এবং voter approval/rejection দেখা যাবে। কোনো password, OTP বা QR secret log করা হবে না। Logs এখন **basic database audit records**; এগুলো এখনো cryptographically tamper-evident নয় (Module 3)।

## 6) Demo-র security checks

- `Voter` হিসেবে `/accounts/staff/voters/` => 403.
- `Voter` হিসেবে `/accounts/security/events/` => 403.
- নতুন admin password login-এর পর authenticator setup/verification ছাড়া dashboard access বন্ধ।
- ৫টি ভুল login attempt => Axes rate limit / 429, cooldown ১৫ মিনিট (একই account ও client/IP অনুযায়ী)।
- ৫টি ভুল MFA code => ১৫ মিনিটের lockout।
- আগে ব্যবহৃত TOTP code আবার submit করলে reject।
- DOB ১৮ বছরের কম থাকলে voter approval blocked; edit করলে approval আবার pending।
- Password change view বর্তমান password যাচাই করে এবং event log করে।

## 7) Production-এ যাওয়ার আগে

এটি **academic prototype**, professional certification নয়। HTTPS, `DJANGO_DEBUG=False`, secret manager, PostgreSQL, backups, supervised MFA enrollment/recovery, session cookie protections, cloud deployment এবং independent security review লাগবে। Django's `runserver` production server নয়। Admin login brute force protection shared rate-limiter deployment/test করতে হবে; SQLite কেবল local demo-এর জন্য।

**Troubleshooting:** `NoReverseMatch` এলে `accounts/urls.py` overlay merge হয়েছে কি না দেখো। CSS missing হলে `python manage.py findstatic css/voting-modern.css` চালাও। `MFA_ENCRYPTION_KEY is missing` এলে Step 2 একবার সম্পন্ন করো।
