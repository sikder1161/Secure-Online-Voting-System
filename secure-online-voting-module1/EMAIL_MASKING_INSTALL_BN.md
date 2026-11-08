# Secure Voting System — Email Address Masking (Bangla Guide)

## কী বদলেছে
- Email verification/OTP page: email আংশিক hidden (`ne**********01@g****.com`)
- Voter dashboard profile: masked email
- Admin voter review table: masked email
- আসল recipient address, SMTP code delivery, email verification ও login process একদম অপরিবর্তিত
- Password reset page আগে থেকেই generic confirmation দেখায়; সেখানে কোনো address প্রকাশ হয় না

**Note:** এটি শুধুমাত্র UI privacy masking; encryption নয়। User-এর account email Django database-এ আগের মতোই থাকবে।

## Install (Windows VS Code — PowerShell)
1. Django runserver বন্ধ করুন (`Ctrl+C`)
2. Project folder-এ যান:

    cd D:\Secure-Online-Voting-System\secure-online-voting-module1

3. Existing templates backup (optional, but recommended):

    Copy-Item .\templates .\templates-backup-before-masking -Recurse -Force

4. Downloads-এ Secure_Voting_Email_Masking_Update.zip রেখে extract:

    Expand-Archive -Path "$env:USERPROFILE\Downloads\Secure_Voting_Email_Masking_Update.zip" -DestinationPath . -Force

5. Check ও tests:

    python manage.py check
    python manage.py test accounts.test_email_masking
    python manage.py test accounts
    python manage.py runserver

6. Browser-এ নতুন OTP request করে masked address দেখুন। তারপর Gmail-এ real email-এ OTP যাচ্ছে কিনা check করুন। Voter dashboard ও Admin review table-তেও masked email দেখা যাবে।

## Compatibility
- No changes to database, migrations, users, SMTP config, OTP generation, passwords, or .env.
- This ZIP contains only 3 HTML template replacements, 1 Python helper, 1 Django template filter (+ __init__), and 1 test file.
- যদি project-এর templates ইতিমধ্যে manual edit করা থাকে, ZIP overwrite করার আগে ফাইলগুলো compare করুন।
- This version is based on the latest delivered Module 1 Password Recovery + Activity update.
