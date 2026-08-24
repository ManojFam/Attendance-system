from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Student, ClassSession


@receiver(post_save, sender=Student)
def create_student_sessions(sender, instance, created, **kwargs):

    current_date = instance.start_date

    weekday_fields = {
        0: 'monday',
        1: 'tuesday',
        2: 'wednesday',
        3: 'thursday',
        4: 'friday',
        5: 'saturday',
        6: 'sunday',
    }

    while current_date <= instance.end_date:

        weekday_field = weekday_fields[current_date.weekday()]

        if getattr(instance.class_group, weekday_field):

            ClassSession.objects.get_or_create(
                class_group=instance.class_group,
                date=current_date
            )

        current_date += timedelta(days=1)