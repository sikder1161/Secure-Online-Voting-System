# Secure Online Voting System - Module 1 (Codespaces)

**Completed features:** voter signup, secure Django login/logout, admin approval of voter identities, and role-based authorization.

> Academic prototype. Not certified or suitable for real public elections. No votes are recorded in Module 1.

## Start fully remotely with GitHub Codespaces

1. Create a **private** GitHub repository and a Codespace.
2. Upload this ZIP to Codespaces using the Explorer, then run `unzip secure-online-voting-module1.zip` from your repository root. (Or upload the extracted files via GitHub's file upload UI, preserving folders.)
3. In the Codespaces terminal:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
python manage.py test accounts
python manage.py runserver 0.0.0.0:8000
```

**Important:** Set `AUTH_USER_MODEL` before your first migration. If you already migrated a separate Django starter project using Django's default User, do **not** copy this code over it and re-run migrations blindly; use a new repository / fresh database for this starter.

4. Open the forwarded **port 8000** from the Codespaces `Ports` tab; set the port visibility **Private**.
5. `/accounts/register/` - register a test voter (role always VOTER).
6. `/accounts/login/` - log in as that voter and see **Pending** status.
7. Log out, log in as the superuser you created, go to `/accounts/staff/voters/`, approve the voter.
8. Log in as the voter again: status becomes **Approved**.

## Cloud PostgreSQL when ready

For the initial browser demo, the app uses **temporary SQLite inside Codespaces**. It is still fully remote, but Codespaces can be deleted and data lost. For the required PostgreSQL architecture:

1. Create a managed PostgreSQL instance (e.g., Neon).
2. In Codespaces, keep credentials in `.env` (gitignored):

```dotenv
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=your-long-random-secret
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

3. Run `python manage.py migrate` again on the new database. It will initialize the new PostgreSQL database; it does **not** move the test voters created in SQLite.
4. Run `python manage.py createsuperuser` for the PostgreSQL DB.

Set `DEBUG=False`, strong secret, allowed hosts, secure deployment configuration and HTTPS before deploying; don't expose dev server or authentication database publicly for real users.

See **QUICK_START_BN.md** for Bangla setup and the live demo checklist.

## Project layout

- `config/` Django configuration
- `accounts/models.py` Custom User and VoterProfile
- `accounts/forms.py` secure voter registration
- `accounts/views.py` dashboards / verification workflow
- `accounts/tests.py` Module 1 automated tests
- `templates/` Bootstrap user interface

## Exact scope

Module 1 verifies **account identity approval**, not election-specific voting rights. Module 2 will introduce `Election`, `Candidate`, `ElectionEligibility`, and vote-participation checks. Do not equate APPROVED identity status with permission to vote in every election.

Additional production controls needed: identity proofing, MFA for staff, login rate limiting, security audit logs (Module 3), HTTPS and cookie policies, email verification, and independent security review.
