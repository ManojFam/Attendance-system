from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Student, ClassSession


@receiver(post_save, sender=Student)
def create_student_sessions(sender, instance, created, **kwargs):

    current_date = instance.start_date

    while current_date <= instance.end_date:

        # Monday = 0
        # Tuesday = 1
        # Wednesday = 2
        if current_date.weekday() in [0, 1, 2]:

            ClassSession.objects.get_or_create(
                class_group=instance.class_group,
                date=current_date
            )

        current_date += timedelta(days=1)