# Attendance System

A Django web app that replaces spreadsheet-based attendance for English
courses (General English, English for Academic Purposes) at a college.
Trainers mark attendance in the browser; admin staff see each student's
attendance percentage across the whole enrolment, without combining monthly
Excel files.

## Features

- **Courses → class groups → students**, each group with its own teaching
  days (e.g. Mon/Tue/Wed or Tue/Thu/Fri).
- **Automatic class sessions** generated from each student's start/end dates
  and their group's schedule. Students joining mid-course share the same
  sessions.
- **Trainer page**: pick a class and date, mark Present / Absent / Leave,
  "set everyone Present" shortcut, whole-class Holiday / Cancelled, jump to
  the previous/next class.
- **Attendance reports** for admin staff: filter by class and status, flag
  students below a minimum % (default 80), CSV export, per-student session
  history.
- **Django admin** with a student dashboard (status, attendance %, unmarked
  sessions) and a class-group form that limits the weekday checkboxes to the
  chosen "days per week".
- **Safe schedule changes**: changing a group's weekdays updates future
  sessions only and never deletes a session that has attendance.
- Role-based access (Trainer group / admin staff) with clean 403 pages.

### Attendance formula

```
Attendance % = Present / (Sessions to date − Holiday − Cancelled) × 100
```

Absent and Leave stay in the denominator. Future sessions are not counted.
Past sessions with no attendance entered yet are shown as **Unmarked**.

## Getting started (Windows)

```cmd
git clone https://github.com/ManojFam/Attendance-system.git
cd Attendance-system
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set a real `SECRET_KEY` (the file shows how to generate one),
then:

```cmd
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Optional demo data (3 classes, 10 students, past attendance, plus logins
`trainer1` and `admin1`):

```cmd
python manage.py seed_demo --users --password "choose-a-password"
```

| URL | Who |
| --- | --- |
| http://127.0.0.1:8000/ | Sends you to the right page for your role |
| /trainer/ | Trainers (users in the **Trainer** group) |
| /reports/ | Admin staff (`is_staff`) |
| /admin/ | Admin staff |

To make someone a trainer: Admin → Users → add the user → put them in the
**Trainer** group (created automatically by the migrations).

## Tests

```cmd
python manage.py test attendance
```

The suite covers validation rules, session generation, schedule changes, the
attendance formula, permissions, the trainer form, reports/CSV and admin
regressions. GitHub Actions runs it on every push.

## Tech

Python 3.13 · Django 6.1 · SQLite (development) · python-dotenv.
PostgreSQL is planned for production.
