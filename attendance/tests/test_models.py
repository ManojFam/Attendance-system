from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from attendance.models import Attendance, ClassGroup, ClassSession, Student

from .helpers import make_course, make_group, make_student


class ClassGroupValidationTests(TestCase):

    def build(self, per_week, days):
        group = ClassGroup(name='G', course=make_course(), class_days_per_week=per_week)
        for field in ClassGroup.WEEKDAY_FIELDS:
            setattr(group, field, field in days)
        return group

    def test_exact_number_of_days_is_valid(self):
        self.build(2, ('monday', 'thursday')).full_clean()

    def test_too_many_days_rejected(self):
        with self.assertRaisesMessage(ValidationError, 'select exactly 2'):
            self.build(2, ('monday', 'tuesday', 'thursday')).full_clean()

    def test_too_few_days_rejected(self):
        with self.assertRaises(ValidationError):
            self.build(3, ('monday',)).full_clean()

    def test_schedule_helpers(self):
        group = self.build(3, ('tuesday', 'thursday', 'friday'))
        self.assertEqual(group.scheduled_weekdays(), {1, 3, 4})
        self.assertEqual(group.schedule_display(), 'Tue, Thu, Fri')


class StudentValidationTests(TestCase):

    def test_end_before_start_rejected(self):
        student = Student(
            student_id='X1', full_name='X', class_group=make_group(),
            start_date=date(2026, 9, 1), end_date=date(2026, 8, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            student.full_clean()
        self.assertIn('end_date', ctx.exception.message_dict)


class AttendanceValidationTests(TestCase):

    def setUp(self):
        self.group = make_group()
        self.student = make_student(self.group)  # 24-31 Aug 2026

    def test_other_group_session_rejected(self):
        other = make_group(name='Other', days=('tuesday', 'thursday', 'friday'))
        session = ClassSession.objects.create(class_group=other, date=date(2026, 8, 25))
        with self.assertRaisesMessage(ValidationError, 'does not match'):
            Attendance(student=self.student, session=session, status='P').full_clean()

    def test_outside_enrolment_rejected(self):
        before = ClassSession.objects.create(class_group=self.group, date=date(2026, 8, 20))
        after = ClassSession.objects.create(class_group=self.group, date=date(2026, 9, 3))

        with self.assertRaisesMessage(ValidationError, 'before'):
            Attendance(student=self.student, session=before, status='P').full_clean()
        with self.assertRaisesMessage(ValidationError, 'after'):
            Attendance(student=self.student, session=after, status='P').full_clean()
