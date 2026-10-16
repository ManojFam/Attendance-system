from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Attendance, ClassSession

from .helpers import ALL_DAYS, make_group, make_student, make_user


class AccessTests(TestCase):

    def setUp(self):
        make_group(name='Daily', days=ALL_DAYS)
        self.trainer = make_user('trainer', trainer=True)
        self.staff = make_user('staff', staff=True)
        self.nobody = make_user('nobody')

    def test_anonymous_redirected_to_login(self):
        for name in ('trainer_attendance', 'attendance_report', 'attendance_report_csv'):
            response = self.client.get(reverse(name))
            self.assertRedirects(
                response, f"/login/?next={reverse(name)}", fetch_redirect_response=False
            )

    def test_non_trainer_gets_403_not_login_loop(self):
        self.client.force_login(self.nobody)
        self.assertEqual(self.client.get(reverse('trainer_attendance')).status_code, 403)

    def test_trainer_cannot_see_reports(self):
        self.client.force_login(self.trainer)
        self.assertEqual(self.client.get(reverse('attendance_report')).status_code, 403)

    def test_superuser_can_use_trainer_page(self):
        self.client.force_login(make_user('root', superuser=True))
        self.assertEqual(self.client.get(reverse('trainer_attendance')).status_code, 200)

    def test_home_routes_by_role(self):
        self.assertRedirects(self.client.get('/'), '/login/', fetch_redirect_response=False)

        self.client.force_login(self.trainer)
        self.assertRedirects(self.client.get('/'), '/trainer/', fetch_redirect_response=False)

        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get('/'), '/reports/', fetch_redirect_response=False)

    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Log in')


class TrainerAttendanceTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.past = self.today - timedelta(days=3)
        self.future = self.today + timedelta(days=3)

        self.group = make_group(name='Daily', days=ALL_DAYS)
        self.s1 = make_student(self.group, 'S1', self.today - timedelta(days=30),
                               self.today + timedelta(days=30), 'Alice')
        self.s2 = make_student(self.group, 'S2', self.today - timedelta(days=30),
                               self.today + timedelta(days=30), 'Bob')
        # Enrols after self.past, so must never get a record for it.
        self.late = make_student(self.group, 'S3', self.today - timedelta(days=1),
                                 self.today + timedelta(days=30), 'Late Joiner')

        self.client.force_login(make_user('trainer', trainer=True))
        self.url = reverse('trainer_attendance')

    def post(self, day, **data):
        payload = {'group': self.group.id, 'date': day.isoformat()}
        payload.update(data)
        return self.client.post(self.url, payload, follow=True)

    def session(self, day):
        return ClassSession.objects.get(class_group=self.group, date=day)

    def test_get_lists_only_enrolled_students(self):
        response = self.client.get(self.url, {'group': self.group.id, 'date': self.past.isoformat()})
        self.assertContains(response, 'Alice')
        self.assertContains(response, 'Bob')
        self.assertNotContains(response, 'Late Joiner')

    def test_saves_individual_attendance(self):
        response = self.post(self.past, **{
            f'attendance_{self.s1.id}': 'P',
            f'attendance_{self.s2.id}': 'A',
        })
        self.assertContains(response, 'Attendance saved for all 2 students')

        statuses = dict(
            Attendance.objects.filter(session=self.session(self.past))
            .values_list('student_id', 'status')
        )
        self.assertEqual(statuses, {self.s1.id: 'P', self.s2.id: 'A'})

    def test_resubmitting_updates_instead_of_duplicating(self):
        self.post(self.past, **{f'attendance_{self.s1.id}': 'P'})
        self.post(self.past, **{f'attendance_{self.s1.id}': 'L'})

        records = Attendance.objects.filter(student=self.s1, session=self.session(self.past))
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.get().status, 'L')

    def test_invalid_or_class_level_status_ignored(self):
        self.post(self.past, **{
            f'attendance_{self.s1.id}': 'X',
            f'attendance_{self.s2.id}': 'H',  # H is whole-class only
        })
        self.assertFalse(Attendance.objects.exists())

    def test_cannot_mark_student_not_enrolled_that_day(self):
        self.post(self.past, **{f'attendance_{self.late.id}': 'P'})
        self.assertFalse(Attendance.objects.filter(student=self.late).exists())

    def test_whole_class_holiday_then_cancelled(self):
        self.post(self.past, **{f'attendance_{self.s1.id}': 'P'})
        self.post(self.past, class_status='H')
        self.post(self.past, class_status='C')

        records = Attendance.objects.filter(session=self.session(self.past))
        self.assertEqual(records.count(), 2)
        self.assertEqual(set(records.values_list('status', flat=True)), {'C'})

    def test_whole_class_rejects_unknown_status(self):
        self.post(self.past, class_status='P')
        self.assertFalse(Attendance.objects.exists())

    def test_future_date_blocks_individual_but_allows_holiday(self):
        response = self.post(self.future, **{f'attendance_{self.s1.id}': 'P'})
        self.assertContains(response, 'cannot be recorded for a future date')
        self.assertFalse(Attendance.objects.exists())

        # All three students (including the late joiner) are enrolled on that date.
        self.post(self.future, class_status='H')
        self.assertEqual(
            Attendance.objects.filter(session=self.session(self.future), status='H').count(), 3
        )

    def test_post_for_date_without_session(self):
        other = make_group(name='Mon only', days=('monday',))
        make_student(other, 'S9', self.today - timedelta(days=30), self.today + timedelta(days=30))
        not_monday = self.past if self.past.weekday() != 0 else self.past - timedelta(days=1)

        response = self.client.post(self.url, {
            'group': other.id, 'date': not_monday.isoformat(), 'class_status': 'H',
        }, follow=True)

        self.assertContains(response, 'No class is scheduled')
        self.assertFalse(Attendance.objects.exists())

    def test_bad_query_parameters_do_not_crash(self):
        response = self.client.get(self.url, {'group': 'abc', 'date': 'not-a-date'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That date was not valid')

    def test_post_without_any_group_does_not_crash(self):
        self.group.student_set.all().delete()
        ClassSession.objects.all().delete()
        self.group.delete()
        response = self.client.post(self.url, {'date': self.past.isoformat()}, follow=True)
        self.assertEqual(response.status_code, 200)


class ReportTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.group = make_group(name='Daily', days=ALL_DAYS)
        self.good = make_student(self.group, 'GOOD1', self.today - timedelta(days=4),
                                 self.today + timedelta(days=30), 'Good Student')
        self.poor = make_student(self.group, 'POOR1', self.today - timedelta(days=4),
                                 self.today + timedelta(days=30), 'Poor Student')

        for session in ClassSession.objects.filter(class_group=self.group, date__lte=self.today):
            Attendance.objects.create(student=self.good, session=session, status='P')
            Attendance.objects.create(student=self.poor, session=session, status='A')

        self.client.force_login(make_user('staff', staff=True))

    def test_report_lists_students_and_flags_low_attendance(self):
        response = self.client.get(reverse('attendance_report'))
        self.assertContains(response, 'Good Student')
        self.assertContains(response, '100.00%')
        self.assertContains(response, 'below-threshold')
        self.assertEqual(response.context['below_count'], 1)

    def test_below_only_filter(self):
        response = self.client.get(reverse('attendance_report'), {'below': '1'})
        self.assertNotContains(response, 'Good Student')
        self.assertContains(response, 'Poor Student')

    def test_csv_export(self):
        response = self.client.get(reverse('attendance_report_csv'))
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment;', response['Content-Disposition'])

        lines = response.content.decode().strip().splitlines()
        self.assertTrue(lines[0].startswith('Student ID,Full name'))
        self.assertEqual(len(lines), 3)
        self.assertTrue(any(line.startswith('GOOD1,') and ',100.00,' in line for line in lines))

    def test_student_detail(self):
        response = self.client.get(reverse('student_detail', args=[self.good.pk]))
        self.assertContains(response, 'Good Student')
        self.assertContains(response, 'Upcoming')
