from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance, ClassSession

from .helpers import make_group, make_student


class SessionGenerationTests(TestCase):

    def test_handoff_example_tue_thu_fri(self):
        """Handoff section 31: GE Test Group, 24-31 Aug 2026."""
        group = make_group(days=('tuesday', 'thursday', 'friday'))
        make_student(group, start=date(2026, 8, 24), end=date(2026, 8, 31))

        dates = list(
            ClassSession.objects.filter(class_group=group)
            .order_by('date').values_list('date', flat=True)
        )

        self.assertEqual(dates, [
            date(2026, 8, 25),
            date(2026, 8, 27),
            date(2026, 8, 28),
        ])

    def test_overlapping_students_share_sessions(self):
        group = make_group()
        make_student(group, 'S1', date(2026, 8, 24), date(2026, 8, 31))
        make_student(group, 'S2', date(2026, 8, 27), date(2026, 9, 4))

        # 25, 27, 28 Aug + 1, 3, 4 Sep = 6 unique sessions
        self.assertEqual(ClassSession.objects.filter(class_group=group).count(), 6)

    def test_resaving_student_does_not_duplicate(self):
        group = make_group()
        student = make_student(group)
        student.save()
        student.save()
        self.assertEqual(ClassSession.objects.filter(class_group=group).count(), 3)


class ScheduleChangeTests(TestCase):
    """Changing a group's weekdays only affects future, empty sessions."""

    def setUp(self):
        self.today = timezone.localdate()
        self.group = make_group(days=('monday', 'tuesday', 'wednesday'))
        self.student = make_student(
            self.group,
            start=self.today - timedelta(days=21),
            end=self.today + timedelta(days=28),
        )

    def weekdays_of(self, queryset):
        return {d.weekday() for d in queryset.values_list('date', flat=True)}

    def test_schedule_change(self):
        sessions = ClassSession.objects.filter(class_group=self.group)

        # Django's week_day lookup: Sunday = 1, Monday = 2 ... Friday = 6
        past_monday = sessions.filter(date__lt=self.today, date__week_day=2).first()
        Attendance.objects.create(student=self.student, session=past_monday, status='P')

        protected_future_monday = sessions.filter(date__gt=self.today, date__week_day=2).first()
        Attendance.objects.create(
            student=self.student, session=protected_future_monday, status='H'
        )

        past_count_before = sessions.filter(date__lt=self.today).count()

        # Switch to Tue / Thu / Fri
        self.group.monday = False
        self.group.wednesday = False
        self.group.thursday = True
        self.group.friday = True
        self.group.full_clean()
        self.group.save()

        # Past sessions untouched.
        self.assertEqual(sessions.filter(date__lt=self.today).count(), past_count_before)

        # Future: only Tue/Thu/Fri, plus the Monday that has attendance.
        future = sessions.filter(date__gte=self.today).exclude(pk=protected_future_monday.pk)
        self.assertEqual(self.weekdays_of(future), {1, 3, 4})
        self.assertTrue(ClassSession.objects.filter(pk=protected_future_monday.pk).exists())

        # New Friday sessions were generated up to the end date.
        self.assertTrue(future.filter(date__week_day=6).exists())
