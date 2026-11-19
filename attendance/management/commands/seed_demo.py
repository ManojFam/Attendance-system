"""
Fill a development database with realistic demo data.

    python manage.py seed_demo
    python manage.py seed_demo --users --password "<choose one>"

Safe to run more than once: existing records are reused, not duplicated.
"""

import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from attendance.models import (
    Attendance,
    ClassGroup,
    ClassSession,
    Course,
    Student,
)
from attendance.permissions import TRAINER_GROUP_NAME


GROUPS = [
    # (course code, group name, weekdays)
    ('GE', 'GE Main Class', ('monday', 'tuesday', 'wednesday')),
    ('GE', 'GE Evening Class', ('tuesday', 'thursday', 'friday')),
    ('EAP', 'EAP Main Class', ('monday', 'wednesday', 'thursday')),
]

# (student id, name, group name, start offset days, length days)
STUDENTS = [
    ('DEMO001', 'Aiko Tanaka', 'GE Main Class', -70, 140),
    ('DEMO002', 'Carlos Mendes', 'GE Main Class', -42, 120),
    ('DEMO003', 'Priya Sharma', 'GE Main Class', -14, 84),
    ('DEMO004', 'Lucas Martin', 'GE Main Class', -120, 100),
    ('DEMO005', 'Minh Nguyen', 'GE Evening Class', -56, 112),
    ('DEMO006', 'Sofia Rossi', 'GE Evening Class', -28, 84),
    ('DEMO007', 'Omar Haddad', 'GE Evening Class', 10, 70),
    ('DEMO008', 'Jae-won Kim', 'EAP Main Class', -63, 126),
    ('DEMO009', 'Isabela Costa', 'EAP Main Class', -35, 98),
    ('DEMO010', 'Arjun Patel', 'EAP Main Class', -21, 70),
]


class Command(BaseCommand):
    help = "Create demo courses, classes, students and past attendance."

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            action='store_true',
            help="Also create demo logins: trainer1 (Trainer) and admin1 (superuser).",
        )
        parser.add_argument(
            '--password',
            help="Password for the demo logins (required with --users).",
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Allow running when DEBUG is False.",
        )

    @transaction.atomic
    def handle(self, *args, **options):

        if not settings.DEBUG and not options['force']:
            raise CommandError(
                "Refusing to seed demo data with DEBUG=False. "
                "Use --force if you really mean it."
            )

        if options['users'] and not options['password']:
            raise CommandError("--users needs --password.")

        today = timezone.localdate()
        rng = random.Random(42)

        courses = {
            'GE': Course.objects.get_or_create(
                code='GE', defaults={'name': 'General English'}
            )[0],
            'EAP': Course.objects.get_or_create(
                code='EAP', defaults={'name': 'English for Academic Purposes'}
            )[0],
        }

        groups = {}

        for course_code, name, days in GROUPS:
            group = ClassGroup.objects.filter(
                name=name, course=courses[course_code]
            ).first()

            if group is None:
                group = ClassGroup(name=name, course=courses[course_code])

                group.class_days_per_week = len(days)

                for field in ClassGroup.WEEKDAY_FIELDS:
                    setattr(group, field, field in days)

                group.full_clean()
                group.save()

            groups[name] = group

        created_students = 0

        for student_id, full_name, group_name, start_offset, length in STUDENTS:
            start_date = today + timedelta(days=start_offset)

            # Saving the student triggers session generation (signals.py).
            _, created = Student.objects.get_or_create(
                student_id=student_id,
                defaults={
                    'full_name': full_name,
                    'class_group': groups[group_name],
                    'start_date': start_date,
                    'end_date': start_date + timedelta(days=length),
                    'entry_test_score': rng.choice([None, 42, 55, 61, 70]),
                    'entry_test_level': rng.choice(['', 'Pre-Intermediate', 'Intermediate']),
                },
            )
            created_students += created

        # Past attendance. The two most recent class days for each group are
        # left unmarked so the "unmarked sessions" feature has something to show.
        marked = 0

        for group in groups.values():
            past_sessions = list(
                ClassSession.objects.filter(
                    class_group=group, date__lt=today
                ).order_by('date')
            )

            holiday_session = past_sessions[len(past_sessions) // 2] if past_sessions else None

            for session in past_sessions[:-2]:
                students = Student.objects.filter(
                    class_group=group,
                    start_date__lte=session.date,
                    end_date__gte=session.date,
                )

                for student in students:
                    if session == holiday_session:
                        status = 'H'
                    else:
                        # Each student gets a stable "reliability" so the
                        # report shows a spread of percentages.
                        reliability = 0.6 + (int(student.student_id[-1]) % 5) * 0.09
                        roll = rng.random()
                        status = 'P' if roll < reliability else ('L' if roll < reliability + 0.08 else 'A')

                    _, created = Attendance.objects.get_or_create(
                        student=student,
                        session=session,
                        defaults={'status': status},
                    )
                    marked += created

        trainer_group, _ = Group.objects.get_or_create(name=TRAINER_GROUP_NAME)

        if options['users']:
            password = options['password']

            trainer, _ = User.objects.get_or_create(username='trainer1')
            trainer.is_staff = False
            trainer.is_superuser = False
            trainer.set_password(password)
            trainer.save()
            trainer.groups.add(trainer_group)

            admin_user, _ = User.objects.get_or_create(username='admin1')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.set_password(password)
            admin_user.save()

            if options['verbosity']:
                self.stdout.write("Demo logins ready: trainer1 (Trainer), admin1 (superuser).")

        if options['verbosity']:
            self.stdout.write(self.style.SUCCESS(
                f"Demo data ready: {len(groups)} classes, "
                f"{created_students} new students, {marked} new attendance records."
            ))
