from datetime import date

from django.test import TestCase

from attendance.models import Attendance, ClassSession
from attendance.services import attendance_summary, student_status

from .helpers import ALL_DAYS, make_group, make_student


class AttendanceSummaryTests(TestCase):
    """Attendance % = P / (N - H - C) x 100"""

    def setUp(self):
        self.group = make_group(name='Daily', days=ALL_DAYS)
        # Monday 5 Jan 2026 .. 1 Mar 2026, a session every day.
        self.student = make_student(
            self.group, start=date(2026, 1, 5), end=date(2026, 3, 1)
        )
        self.today = date(2026, 1, 11)  # 7 sessions to date (5..11 Jan)

    def mark(self, day, status):
        session = ClassSession.objects.get(class_group=self.group, date=date(2026, 1, day))
        Attendance.objects.create(student=self.student, session=session, status=status)

    def test_formula(self):
        for day, status in [(5, 'P'), (6, 'P'), (7, 'A'), (8, 'L'), (9, 'H'), (10, 'C')]:
            self.mark(day, status)
        # 11 Jan left unmarked

        summary = attendance_summary(self.student, today=self.today)

        self.assertEqual(summary.total_sessions, 7)
        self.assertEqual(summary.eligible_sessions, 5)  # 7 - H - C
        self.assertEqual(summary.unmarked, 1)
        self.assertEqual((summary.present, summary.absent, summary.leave), (2, 1, 1))
        self.assertAlmostEqual(summary.percentage, 40.0)
        self.assertEqual(summary.percentage_display, '40.00%')

    def test_future_sessions_not_counted(self):
        self.mark(5, 'P')
        summary = attendance_summary(self.student, today=date(2026, 1, 5))
        self.assertEqual(summary.total_sessions, 1)
        self.assertEqual(summary.percentage, 100.0)

    def test_not_started(self):
        summary = attendance_summary(self.student, today=date(2026, 1, 1))
        self.assertEqual(summary.total_sessions, 0)
        self.assertEqual(summary.percentage_display, '0.00%')

    def test_all_holiday_gives_zero_not_error(self):
        self.mark(5, 'H')
        summary = attendance_summary(self.student, today=date(2026, 1, 5))
        self.assertEqual(summary.eligible_sessions, 0)
        self.assertEqual(summary.percentage, 0.0)

    def test_completed_student_uses_end_date(self):
        summary = attendance_summary(self.student, today=date(2026, 12, 31))
        self.assertEqual(summary.total_sessions, 56)  # 5 Jan .. 1 Mar

    def test_student_status(self):
        self.assertEqual(student_status(self.student, date(2026, 1, 1)), 'Not Started')
        self.assertEqual(student_status(self.student, date(2026, 2, 1)), 'Active')
        self.assertEqual(student_status(self.student, date(2026, 3, 2)), 'Completed')
