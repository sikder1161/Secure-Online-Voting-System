# Date of Birth + 18+ Voting Rule (Module 1 Update)

## Exactly what this update does
- Adds a Date of Birth field during voter registration.
- Under-18 users may register for a user account, but cannot be approved to vote.
- Admin approval requires age 18+ AND a birth date.
- Dashboard shows DOB and age status. Edit profile allows existing accounts to add DOB.
- Changing DOB or other identity details resets an existing approval to Pending.
- Model `VoterProfile.can_vote` is False unless active, approved and at least 18.
- Module 2 MUST call this clearance check again during the actual vote-casting transaction, plus election-specific eligibility, schedule, and duplicate-vote safeguards. This module does NOT implement casting yet.

## Installation (VS Code PowerShell)
1. Stop the Django server: Ctrl+C.
2. Back up your database (`db.sqlite3`) before replacing code.
3. Extract the ZIP into `D:\Secure-Online-Voting-System\secure-online-voting-module1` (same folder as `manage.py`), overwrite matching files.
4. Run:

```powershell
cd D:\Secure-Online-Voting-System\secure-online-voting-module1
python manage.py check
python manage.py migrate
python manage.py test accounts
python manage.py runserver
```

## IMPORTANT for existing approved voter
Legacy accounts have no DOB. This is deliberate (safe migration with no fabricated DOB).
The voter must log in, click Edit profile, add DOB, and Save. Their approval becomes Pending.
The administrator checks the DOB against real institutional proof, then approves again if age 18+.
No existing users, passwords or votes are deleted by the update.

## Security / limits
A self-entered DOB does not prove age; staff must verify evidence before approval.
You should not copy DOB into public audit logs or show it on public election result pages.
For an actual election, check legal/organizational age requirements and the election's applicable cutoff date. This project uses age on the current local date for account clearance.
