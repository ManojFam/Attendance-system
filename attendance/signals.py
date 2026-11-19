from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ClassGroup, Student
from .services import generate_sessions, sync_group_schedule


@receiver(post_save, sender=Student)
def create_student_sessions(sender, instance, created, raw=False, **kwargs):
    """
    When a student is saved, make sure their class group has a session
    for every scheduled weekday in the student's enrolment period.
    """

    # Skip while loading fixtures (loaddata).
    if raw:
        return

    generate_sessions(
        instance.class_group,
        instance.start_date,
        instance.end_date,
    )


@receiver(post_save, sender=ClassGroup)
def update_group_sessions(sender, instance, created, raw=False, **kwargs):
    """
    When a class group's weekdays change, bring FUTURE sessions in line
    with the new schedule. Past sessions and any session that already has
    attendance are never deleted.
    """

    # A brand new group has no students yet.
    if raw or created:
        return

    sync_group_schedule(instance)
