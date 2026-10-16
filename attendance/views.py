import csv
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import Attendance, ClassGroup, ClassSession, Student
from .permissions import (
    is_report_viewer,
    is_trainer,
    report_viewer_required,
    trainer_required,
)
from .services import attendance_summary, student_status


DEFAULT_ATTENDANCE_THRESHOLD = 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value):
    """Return a date for 'YYYY-MM-DD', or None if missing/invalid."""
    if not value:
        return None

    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _trainer_url(group, selected_date):
    query = {'date': selected_date.isoformat()}

    if group:
        query['group'] = group.id

    return f"{reverse('trainer_attendance')}?{urlencode(query)}"


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

def home(request):
    """Send each kind of user to the page they actually use."""

    if not request.user.is_authenticated:
        return redirect('login')

    if is_trainer(request.user):
        return redirect('trainer_attendance')

    if is_report_viewer(request.user):
        return redirect('attendance_report')

    raise PermissionDenied


# ---------------------------------------------------------------------------
# Trainer attendance
# ---------------------------------------------------------------------------

@trainer_required
def trainer_attendance(request):

    data = request.POST if request.method == 'POST' else request.GET
    today = timezone.localdate()

    selected_date = _parse_date(data.get('date'))

    if selected_date is None:
        if data.get('date'):
            messages.error(
                request,
                "That date was not valid, so today is shown instead."
            )
        selected_date = today

    class_groups = ClassGroup.objects.select_related(
        'course'
    ).order_by('course__code', 'name')

    selected_group = None
    selected_group_id = _parse_int(data.get('group'))

    if selected_group_id:
        selected_group = class_groups.filter(
            id=selected_group_id
        ).first()

    if not selected_group:
        selected_group = class_groups.first()

    students = Student.objects.none()
    session = None

    if selected_group:

        # Only students enrolled on this date, in this group.
        students = Student.objects.filter(
            class_group=selected_group,
            start_date__lte=selected_date,
            end_date__gte=selected_date,
        ).order_by('full_name')

        session = ClassSession.objects.filter(
            class_group=selected_group,
            date=selected_date,
        ).first()

    if request.method == 'POST':

        if session is None:
            messages.error(
                request,
                "No class is scheduled for this date, "
                "so nothing was saved."
            )
        else:
            _save_attendance(
                request,
                session,
                students,
                is_future=selected_date > today,
            )

        return redirect(_trainer_url(selected_group, selected_date))

    attendance_data = {}

    if session:
        attendance_data = dict(
            Attendance.objects.filter(
                session=session,
                student__in=students,
            ).values_list('student_id', 'status')
        )

    students = list(students)

    for student in students:
        student.saved_status = attendance_data.get(student.id)

    marked_count = sum(1 for s in students if s.saved_status)

    previous_session = next_session = None

    if selected_group:
        group_sessions = ClassSession.objects.filter(
            class_group=selected_group
        )
        previous_session = group_sessions.filter(
            date__lt=selected_date
        ).order_by('-date').first()
        next_session = group_sessions.filter(
            date__gt=selected_date
        ).order_by('date').first()

    context = {
        'students': students,
        'today': selected_date,
        'actual_today': today,
        'is_future': selected_date > today,
        'session': session,
        'class_groups': class_groups,
        'selected_group': selected_group,
        'marked_count': marked_count,
        'unmarked_count': len(students) - marked_count,
        'previous_session': previous_session,
        'next_session': next_session,
    }

    return render(
        request,
        'attendance/trainer_attendance.html',
        context
    )


def _save_attendance(request, session, students, is_future):
    """Handle both the whole-class buttons and the per-student form."""

    class_status = request.POST.get('class_status')

    # ---- Whole class Holiday / Cancelled ----
    if class_status:

        if class_status not in Attendance.CLASS_STATUSES:
            messages.error(request, "Unknown class status.")
            return

        # update_or_create: an existing record for this student/session is
        # changed (e.g. H -> C) rather than duplicated.
        with transaction.atomic():
            for student in students:
                Attendance.objects.update_or_create(
                    student=student,
                    session=session,
                    defaults={'status': class_status},
                )

        label = dict(Attendance.STATUS_CHOICES)[class_status]
        messages.success(
            request,
            f"Whole class marked as {label} "
            f"({len(students)} students)."
        )
        return

    # ---- Individual Present / Absent / Leave ----
    if is_future:
        messages.error(
            request,
            "Present, Absent and Leave cannot be recorded for a future "
            "date. You can still mark the whole class Holiday or Cancelled."
        )
        return

    saved = 0

    with transaction.atomic():
        for student in students:
            status = request.POST.get(f'attendance_{student.id}')

            if status not in Attendance.INDIVIDUAL_STATUSES:
                continue

            Attendance.objects.update_or_create(
                student=student,
                session=session,
                defaults={'status': status},
            )
            saved += 1

    total = len(students)

    if saved == 0:
        messages.warning(request, "No attendance was selected.")
    elif saved < total:
        messages.warning(
            request,
            f"Attendance saved for {saved} of {total} students. "
            f"{total - saved} still need a status."
        )
    else:
        messages.success(
            request,
            f"Attendance saved for all {total} students."
        )


# ---------------------------------------------------------------------------
# Reports (admin staff)
# ---------------------------------------------------------------------------

STATUS_FILTER_CHOICES = [
    ('active', 'Active'),
    ('not_started', 'Not Started'),
    ('completed', 'Completed'),
    ('all', 'All students'),
]


def _report_filters(request):
    status = request.GET.get('status', 'active')

    if status not in dict(STATUS_FILTER_CHOICES):
        status = 'active'

    threshold = _parse_int(request.GET.get('threshold'))

    if threshold is None or not 0 <= threshold <= 100:
        threshold = DEFAULT_ATTENDANCE_THRESHOLD

    return {
        'group_id': _parse_int(request.GET.get('group')),
        'status': status,
        'threshold': threshold,
        'below_only': request.GET.get('below') == '1',
    }


def _report_rows(filters, today):
    students = Student.objects.select_related(
        'class_group__course'
    ).order_by('class_group__course__code', 'class_group__name', 'full_name')

    if filters['group_id']:
        students = students.filter(class_group_id=filters['group_id'])

    if filters['status'] == 'active':
        students = students.filter(start_date__lte=today, end_date__gte=today)
    elif filters['status'] == 'not_started':
        students = students.filter(start_date__gt=today)
    elif filters['status'] == 'completed':
        students = students.filter(end_date__lt=today)

    rows = []

    for student in students:
        summary = attendance_summary(student, today)

        below_threshold = (
            summary.eligible_sessions > 0
            and summary.percentage < filters['threshold']
        )

        if filters['below_only'] and not below_threshold:
            continue

        rows.append({
            'student': student,
            'status': student_status(student, today),
            'summary': summary,
            'below_threshold': below_threshold,
        })

    return rows


@report_viewer_required
def attendance_report(request):
    today = timezone.localdate()
    filters = _report_filters(request)
    rows = _report_rows(filters, today)

    context = {
        'rows': rows,
        'filters': filters,
        'status_choices': STATUS_FILTER_CHOICES,
        'class_groups': ClassGroup.objects.select_related(
            'course'
        ).order_by('course__code', 'name'),
        'below_count': sum(1 for row in rows if row['below_threshold']),
        'unmarked_total': sum(row['summary'].unmarked for row in rows),
        'today': today,
        'export_query': request.GET.urlencode(),
    }

    return render(request, 'attendance/report.html', context)


@report_viewer_required
def attendance_report_csv(request):
    today = timezone.localdate()
    filters = _report_filters(request)
    rows = _report_rows(filters, today)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_report_{today.isoformat()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Student ID', 'Full name', 'Course', 'Class group',
        'Start date', 'End date', 'Status',
        'Present', 'Absent', 'Leave', 'Holiday', 'Cancelled', 'Unmarked',
        'Sessions to date', 'Eligible sessions', 'Attendance %',
        'Below threshold',
        'Entry test score', 'Entry test level',
        'Exit test score', 'Exit test level',
    ])

    for row in rows:
        student = row['student']
        summary = row['summary']

        writer.writerow([
            student.student_id,
            student.full_name,
            student.class_group.course.code,
            student.class_group.name,
            student.start_date.isoformat(),
            student.end_date.isoformat(),
            row['status'],
            summary.present,
            summary.absent,
            summary.leave,
            summary.holiday,
            summary.cancelled,
            summary.unmarked,
            summary.total_sessions,
            summary.eligible_sessions,
            f"{summary.percentage:.2f}",
            'Yes' if row['below_threshold'] else 'No',
            student.entry_test_score if student.entry_test_score is not None else '',
            student.entry_test_level,
            student.exit_test_score if student.exit_test_score is not None else '',
            student.exit_test_level,
        ])

    return response


@report_viewer_required
def student_detail(request, pk):
    today = timezone.localdate()

    student = get_object_or_404(
        Student.objects.select_related('class_group__course'),
        pk=pk,
    )

    sessions = ClassSession.objects.filter(
        class_group=student.class_group,
        date__gte=student.start_date,
        date__lte=student.end_date,
    ).order_by('date')

    statuses = dict(
        Attendance.objects.filter(
            student=student,
            session__in=sessions,
        ).values_list('session_id', 'status')
    )

    status_labels = dict(Attendance.STATUS_CHOICES)

    records = []

    for session in sessions:
        code = statuses.get(session.id)

        if code:
            label = status_labels[code]
        elif session.date > today:
            label = 'Upcoming'
        else:
            label = 'Unmarked'

        records.append({
            'session': session,
            'code': code or '',
            'label': label,
        })

    context = {
        'student': student,
        'status': student_status(student, today),
        'summary': attendance_summary(student, today),
        'records': records,
        'today': today,
    }

    return render(request, 'attendance/student_detail.html', context)
