# Module 1: GitHub Codespaces Quick Start (বাংলা)

## 1. Codespaces খুলুন

GitHub-এ private repository তৈরি করে **Code > Codespaces > Create codespace on main** চাপুন।

## 2. ZIP upload এবং extract করুন

Codespaces Explorer-এর root folder-এ `secure-online-voting-module1.zip` upload করুন। তারপর Terminal-এ:

```bash
unzip -o secure-online-voting-module1.zip
```

**সতর্কতা:** এই ZIP-এ project-এর `config/settings.py` এবং `manage.py` আছে। আগে থেকে Django project তৈরি থাকলে প্রয়োজনীয় file overwrite হতে পারে। সবচেয়ে সহজ উপায় হলো নতুন repository বা খালি Codespace নেওয়া। **আগে database migrate করে থাকলে custom user model বসানোর আগে fresh DB প্রয়োজন।**

## 3. Virtual environment ও dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

`.env`-এ একটি strong random `DJANGO_SECRET_KEY` value দিন; এটি কখনও GitHub-এ commit করবেন না। Demo-এর জন্য `DJANGO_DEBUG=True` থাকবে।

## 4. Database table বানান এবং administrator account তৈরি করুন

```bash
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
```

Superuser-এর username/password মনে রাখবেন। Terminal-এ টাইপ করা password দেখা যাবে না, এটি স্বাভাবিক।

## 5. Automated tests ও development server

```bash
python manage.py test accounts
python manage.py runserver 0.0.0.0:8000
```

Codespaces-এর **Ports** tab থেকে port **8000**-এর URL browser-এ খুলুন। Port **Private** রাখুন।

## 6. Module 1 live demo

1. `/accounts/register/` - নতুন voter account খুলুন। Status **Pending** হবে।
2. `/accounts/login/` - voter login করে dashboard দেখুন।
3. Logout করুন; `createsuperuser` দিয়ে বানানো admin account-এ login করুন।
4. `/accounts/staff/voters/` - voter-এর **Approve** button চাপুন।
5. Voter-এ আবার login করুন; status **Approved** দেখাবে।
6. Voter account দিয়ে admin voters URL খুলে দেখুন; **403 Forbidden** হওয়া উচিত।

## 7. PostgreSQL (পরের ধাপ)

এখন দ্রুত demo-র জন্য Codespaces-এর মধ্যে SQLite ব্যবহৃত হচ্ছে। পরে cloud PostgreSQL connection string `.env`-এ `DATABASE_URL=postgresql://...` যোগ করে PostgreSQL ব্যবহার করা যাবে। এটা real voter data নয়, শুধু **academic prototype**।

**Module 2:** Election creation, candidate management, election-specific voter eligibility, secure vote casting ও duplicate-vote prevention।
