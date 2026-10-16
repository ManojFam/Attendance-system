# Attendance System — notes for Claude

Django 6.1 / Python 3.13 app that replaces the Excel attendance process for
English courses (GE, EAP) at a college/RTO. Portfolio project: the developer
wants to understand every change, so explain *why*, work one feature at a
time, and give whole files when a Python file changes.

## Commands (Windows, from the repo root)

```cmd
.venv\Scripts\activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test attendance
python manage.py runserver
python manage.py seed_demo --users --password "<pick one>"   :: dev data only
```

## Layout

- `attendance/models.py` — Course, ClassGroup (7 weekday booleans +
  `class_days_per_week`), Student, ClassSession, Attendance.
- `attendance/services.py` — **single source** for session generation,
  schedule-change sync and the attendance formula. Admin, views and reports
  all call it; do not re-implement the formula elsewhere.
- `attendance/signals.py` — Student save → generate sessions;
  ClassGroup save → `sync_group_schedule`.
- `attendance/permissions.py` — `trainer_required` (Trainer group or
  superuser), `report_viewer_required` (is_staff). Non-permitted logged-in
  users get 403, not a login redirect.
- `attendance/views.py` — `/` (routes by role), `/trainer/`, `/reports/`,
  `/reports/export.csv`, `/reports/student/<pk>/`.
- `attendance/static/attendance/admin/class_days_limit.js` — admin UX
  that limits weekday checkboxes. Backend `ClassGroup.clean()` stays the rule.
- `attendance/tests/` — Django TestCase suite; run before every commit.

## Business rules that must not change silently

- Statuses: P, A, L (per student), H, C (whole class only).
- Attendance % = P / (N − H − C) × 100, N = sessions from start date to
  min(today, end date). Future sessions never count.
- **Unmarked past sessions currently count in N** (behave like absences).
  They are shown separately ("Unmarked") — changing the formula needs a
  business decision first.
- A student only gets attendance for their own class group, within their
  start/end dates. One session per (group, date); one attendance per
  (student, session). Keep both unique constraints.
- Never delete a ClassSession that has attendance. Schedule changes only
  affect sessions from today onwards.
- P/A/L cannot be entered for a future date; H/C can (planned holidays).
- Keep the null-checks in `StudentAdmin` — the Add page crashes without them.

## Config

`.env` (never committed; see `.env.example`): SECRET_KEY (required), DEBUG
(defaults to False), ALLOWED_HOSTS, TIME_ZONE (defaults Australia/Sydney —
"today" for attendance depends on it).
