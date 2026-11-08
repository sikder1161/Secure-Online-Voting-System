# Secure Voting System - Modern UI Update (বাংলা নির্দেশনা)

এই update **শুধু frontend** বদলাবে: 9টি HTML template, 1টি icon partial, CSS, JavaScript।

- Database, `.env`, Python models, migrations, username, passwords, approval, DOB ও 18+ validation **পরিবর্তন হবে না**।
- আগে DOB & 18+ update এবং Edit Profile / Change Password feature install করা থাকতে হবে।
- Module 2-এর নির্বাচন/ভোট সংক্রান্ত option গুলো এখন **Coming Soon**; এগুলো কার্যকর feature নয়।

## Update করার ধাপ (Windows VS Code PowerShell)

1. Terminal-এ server চালু থাকলে `Ctrl + C` দিয়ে বন্ধ করো।
2. Current project folder-এ যাও:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
```

3. Backup রাখো (নিজের দরকার মতো path পরিবর্তন করতে পারো):

```powershell
Copy-Item -Path .\templates -Destination .\templates-backup-before-modern -Recurse -Force
```

4. `secure-voting-modern-ui-update.zip` file-টি **Downloads** folder-এ রাখো। তারপর:

```powershell
Expand-Archive -Path "$env:USERPROFILE\Downloads\secure-voting-modern-ui-update.zip" -DestinationPath . -Force
```

5. Verify & run:

```powershell
Test-Path .\static\css\voting-modern.css
python manage.py check
python manage.py test accounts
python manage.py runserver
```

`Test-Path` এর output `True` হলে CSS file বসেছে।

6. Browser-এ `http://127.0.0.1:8000/accounts/dashboard/` খোলো। পুরনো CSS দেখালে `Ctrl + Shift + R` চাপো।

## কীভাবে test করবে

- Voter দিয়ে login: Dashboard, Edit Profile, Change Password check করো।
- Birth date ও age info check করো। DOB বদলালে approval আবার Pending হবে।
- Admin দিয়ে login: Total, Pending, Approved, Rejected counts দেখো।
- `Voter management` থেকে review queue-তে যাও। Under-18 voter-এর **Approve** disabled থাকবে।
- Voter দিয়ে admin queue খুললে **403 Forbidden** হবে, এটাই expected।
- Mobile browser-এ sidebar menu open/close করে দেখো।

## সাধারণ সমস্যা

- `NoReverseMatch` edit_profile: পুরনো Python files আছে। আগের DOB update-এর `accounts/urls.py` / `accounts/views.py` install ও পরীক্ষা করো।
- `TemplateDoesNotExist`: `templates/` folder নিশ্চিত করো; URL থেকে project root ঠিক কি না দেখো।
- CSS আসে না: project root-এ `static/css/voting-modern.css` আছে কি না দেখো।
- `ERR_CONNECTION_REFUSED`: terminal-এ `python manage.py runserver` আবার চালাও।

## Important

এটি academic prototype-এর **visual design update**। নতুন design নিরাপত্তা নিশ্চিত করে না। Actual voting, encryption ও election-specific eligibility পরবর্তী Modules-এ implement ও test করতে হবে।
