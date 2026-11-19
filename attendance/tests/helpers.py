from datetime import date

from django.contrib.auth.models import Group, User

from attendance.models import ClassGroup, Course, Student
from attendance.permissions import TRAINER_GROUP_NAME


ALL_DAYS = ClassGroup.WEEKDAY_FIELDS


def make_course(code='GE', name='General English'):
    return Course.objects.get_or_create(code=code, defaults={'name': name})[0]


def make_group(name='GE Test Group', days=('tuesday', 'thursday', 'friday'), course=None):
    group = ClassGroup(
        name=name,
        course=course or make_course(),
        class_days_per_week=len(days),
    )

    for field in ALL_DAYS:
        setattr(group, field, field in days)

    group.full_clean()
    group.save()
    return group


def make_student(group, student_id='S001', start=date(2026, 8, 24), end=date(2026, 8, 31),
                 full_name='Test Student'):
    return Student.objects.create(
        student_id=student_id,
        full_name=full_name,
        class_group=group,
        start_date=start,
        end_date=end,
    )


def make_user(username, trainer=False, staff=False, superuser=False):
    user = User.objects.create_user(username=username, password='test-pass-123')
    user.is_staff = staff or superuser
    user.is_superuser = superuser
    user.save()

    if trainer:
        user.groups.add(Group.objects.get_or_create(name=TRAINER_GROUP_NAME)[0])

    return user
