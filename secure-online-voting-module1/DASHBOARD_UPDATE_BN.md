# Module 1 Dashboard Upgrade - Windows VS Code

এই update-এ **আগের database বা account delete হবে না**। এটি শুধু Django source code, templates এবং tests update করে।

## Update কী কী পরিবর্তন করবে

- Voter Dashboard: name, email, role, institutional ID, department, last login, account creation date, verification status, review date।
- Voter actions: Edit profile, Change password, Review verification status।
- Profile-এর name বা department বদলালে identity approval আবার `PENDING` হবে। Institutional ID বা email এই page থেকে edit করা যাবে না।
- Admin Dashboard: Total, Pending, Approved, Rejected; recent pending voters ও shortcut links।
- Module 2-এর featureগুলো `Coming in Module 2` লেখা দিয়ে দেখানো হয়েছে; এগুলো এখনো চালু হয়নি।

## পুরনো প্রজেক্টে update apply করার নিয়ম

1. `secure-voting-dashboard-upgrade.zip` Downloads folder-এ download করো।
2. VS Code-এ আগে চালু থাকা server `Ctrl+C` দিয়ে stop করো।
3. Terminal-এ:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
Expand-Archive -Path "$env:USERPROFILE\Downloads\secure-voting-dashboard-upgrade.zip" -DestinationPath . -Force
python manage.py check
python manage.py test accounts
python manage.py runserver
```

**এখানে `.env` বা `db.sqlite3` পরিবর্তন হবে না।** `makemigrations`/`migrate` লাগবে না, কারণ database models পরিবর্তন হয়নি।

4. Browser-এ `http://127.0.0.1:8000/accounts/dashboard/` refresh করো।
5. Voter account দিয়ে **Edit profile** এবং **Change password** চালিয়ে দেখো।
6. Admin account দিয়ে Pending/Approved/Rejected filters দেখো।

### ZIP অন্য folder-এ download হলে

VS Code-এর Terminal-এ zip file-এর full path দিয়ে `Expand-Archive -Path "..." -DestinationPath . -Force` চালাও।

### Important

এটি একটি university academic prototype। Module 1-এ vote/election/ballot তৈরি বা count হয় না। Production voting system হিসেবে ব্যবহার করার আগে security testing, independent review, proper authentication controls, etc. প্রয়োজন।
