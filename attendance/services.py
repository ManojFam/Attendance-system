"""
Business logic shared by the admin, trainer page, reports and signals.

Keeping it here means the attendance formula and the session-generation
rules exist in exactly one place.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Attendance, ClassSession, Student


# ---------------------------------------------------------------------------
# Session generation
# ---------------------------------------------------------------------------

def generate_sessions(class_group, start_date, end_date):
    """
    Create one ClassSession per scheduled weekday between start_date and
    end_date (inclusive) for the class group.

    Existing sessions are left alone, so several students in the same group
    still share one session per date. The unique constraint on
    (class_group, date) is the final safety net (ignore_conflicts).

    Returns the number of sessions created.
    """
    weekdays = class_group.scheduled_weekdays()

    if not weekdays or end_date < start_date:
        return 0

    wanted_dates = []
    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() in weekdays:
            wanted_dates.append(current_date)
        current_date += timedelta(days=1)

    existing_dates = set(
        ClassSession.objects.filter(
            class_group=class_group,
            date__gte=start_date,
            date__lte=end_date,
        ).values_list('date', flat=True)
    )

    new_sessions = [
        ClassSession(class_group=class_group, date=session_date)
        for session_date in wanted_dates
        if session_date not in existing_dates
    ]

    ClassSession.objects.bulk_create(
        new_sessions,
        ignore_conflicts=True,
    )

    return len(new_sessions)


def remove_unscheduled_sessions(class_group, from_date):
    """
    Delete sessions on or after from_date that fall on a weekday the group
    no longer teaches.

    Sessions that already have ANY attendance record are never deleted,
    so historical data is always preserved.

    Returns the number of sessions deleted.
    """
    weekdays = class_group.scheduled_weekdays()

    empty_future_sessions = ClassSession.objects.filter(
        class_group=class_group,
        date__gte=from_date,
        attendance__isnull=True,
    )

    ids_to_delete = [
        session.pk
        for session in empty_future_sessions
        if session.date.weekday() not in weekdays
    ]

    if not ids_to_delete:
        return 0

    deleted, _ = ClassSession.objects.filter(
        pk__in=ids_to_delete
    ).delete()

    return deleted


def sync_group_schedule(class_group, today=None):
    """
    Called after a class group's weekdays change.

    - Past sessions are never touched.
    - From today onwards, sessions are created for the new weekdays
      (for every student still enrolled) and empty sessions on dropped
      weekdays are removed.

    Returns (created, removed).
    """
    today = today or timezone.localdate()

    created = 0

    current_students = Student.objects.filter(
        class_group=class_group,
        end_date__gte=today,
    )

    for student in current_students:
        created += generate_sessions(
            class_group,
            max(student.start_date, today),
            student.end_date,
        )

    removed = remove_unscheduled_sessions(class_group, today)

    return created, removed


# ---------------------------------------------------------------------------
# Attendance percentage
# ---------------------------------------------------------------------------

@dataclass
class AttendanceSummary:
    present: int = 0
    absent: int = 0
    leave: int = 0
    holiday: int = 0
    cancelled: int = 0
    unmarked: int = 0
    total_sessions: int = 0
    eligible_sessions: int = 0
    percentage: float = 0.0

    @property
    def percentage_display(self):
        return f"{self.percentage:.2f}%"


def attendance_summary(student, today=None):
    """
    Attendance % = P / (N - H - C) x 100

    N = the group's sessions from the student's start date up to
        min(today, end date), so future sessions never lower the result.

    Absent, Leave and (for now) Unmarked sessions all stay in the
    denominator. Unmarked is reported separately so admin can see when a
    low percentage is caused by attendance that has not been entered yet.
    """
    today = today or timezone.localdate()

    calculation_end_date = min(today, student.end_date)

    # Student has not started yet.
    if calculation_end_date < student.start_date:
        return AttendanceSummary()

    sessions = ClassSession.objects.filter(
        class_group_id=student.class_group_id,
        date__gte=student.start_date,
        date__lte=calculation_end_date,
    )

    total_sessions = sessions.count()

    counts = dict(
        Attendance.objects.filter(
            student=student,
            session__in=sessions,
        )
        .order_by()
        .values_list('status')
        .annotate(total=Count('id'))
    )

    present = counts.get('P', 0)
    holiday = counts.get('H', 0)
    cancelled = counts.get('C', 0)

    eligible_sessions = total_sessions - holiday - cancelled

    if eligible_sessions > 0:
        percentage = (present / eligible_sessions) * 100
    else:
        percentage = 0.0

    return AttendanceSummary(
        present=present,
        absent=counts.get('A', 0),
        leave=counts.get('L', 0),
        holiday=holiday,
        cancelled=cancelled,
        unmarked=total_sessions - sum(counts.values()),
        total_sessions=total_sessions,
        eligible_sessions=eligible_sessions,
        percentage=percentage,
    )


def student_status(student, today=None):
    """Return 'Not Started', 'Active' or 'Completed'."""
    today = today or timezone.localdate()

    if today < student.start_date:
        return "Not Started"

    if today > student.end_date:
        return "Completed"

    return "Active"
