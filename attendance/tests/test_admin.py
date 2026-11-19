from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from attendance.models import Attendance, ClassGroup, Student

from .helpers import make_course, make_group, make_student, make_user


class AdminTests(TestCase):

    def setUp(self):
        self.client.force_login(make_user('root', superuser=True))

    def test_student_add_page_does_not_crash(self):
        """Regression: readonly attendance % used to crash on an unsaved student."""
        response = self.client.get(reverse('admin:attendance_student_add'))
        self.assertEqual(response.status_code, 200)

    def test_student_changelist_and_change_page(self):
        student = make_student(make_group())
        self.assertEqual(
            self.client.get(reverse('admin:attendance_student_changelist')).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse('admin:attendance_student_change', args=[student.pk])).status_code,
            200,
        )

    def test_class_group_form_loads_day_limit_script(self):
        response = self.client.get(reverse('admin:attendance_classgroup_add'))
        self.assertContains(response, 'attendance/admin/class_days_limit.js')

    def test_class_group_backend_validation_still_applies(self):
        """Even if the JavaScript is bypassed, the wrong number of days is refused."""
        course = make_course()
        response = self.client.post(reverse('admin:attendance_classgroup_add'), {
            'name': 'Bad group',
            'course': course.pk,
            'class_days_per_week': 2,
            'monday': 'on', 'tuesday': 'on', 'wednesday': 'on',
        })
        self.assertContains(response, 'Please select exactly 2 class days')
        self.assertFalse(ClassGroup.objects.filter(name='Bad group').exists())


class SeedDemoTests(TestCase):

    def test_seed_is_idempotent(self):
        call_command('seed_demo', '--force', '--users', '--password', 'demo-pass-123', verbosity=0)
        counts = (Student.objects.count(), Attendance.objects.count())

        call_command('seed_demo', '--force', verbosity=0)

        self.assertEqual(counts[0], 10)
        self.assertGreater(counts[1], 0)
        self.assertEqual((Student.objects.count(), Attendance.objects.count()), counts)
