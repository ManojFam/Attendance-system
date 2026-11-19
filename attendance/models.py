from django.db import models
from django.core.exceptions import ValidationError


class Course(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class ClassGroup(models.Model):

    CLASS_DAYS_CHOICES = [
        (1, '1 day per week'),
        (2, '2 days per week'),
        (3, '3 days per week'),
        (4, '4 days per week'),
        (5, '5 days per week'),
        (6, '6 days per week'),
        (7, '7 days per week'),
    ]

    # Index matches date.weekday(): Monday = 0 ... Sunday = 6
    WEEKDAY_FIELDS = (
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    )

    name = models.CharField(max_length=100)

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )

    class_days_per_week = models.PositiveSmallIntegerField(
        choices=CLASS_DAYS_CHOICES,
        default=3
    )

    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    def scheduled_weekdays(self):
        """Return the set of weekday numbers (0 = Monday) this group teaches."""
        return {
            index
            for index, field in enumerate(self.WEEKDAY_FIELDS)
            if getattr(self, field)
        }

    def schedule_display(self):
        """Short label such as 'Tue, Thu, Fri'."""
        return ", ".join(
            field[:3].title()
            for field in self.WEEKDAY_FIELDS
            if getattr(self, field)
        ) or "—"

    def clean(self):

        selected_days = [
            getattr(self, field)
            for field in self.WEEKDAY_FIELDS
        ]

        number_of_selected_days = sum(selected_days)

        if number_of_selected_days != self.class_days_per_week:
            raise ValidationError(
                f"Please select exactly "
                f"{self.class_days_per_week} class days. "
                f"You currently selected "
                f"{number_of_selected_days}."
            )

    def __str__(self):
        return f"{self.name} - {self.course.code}"


class Student(models.Model):
    student_id = models.CharField(
        max_length=20,
        unique=True
    )

    full_name = models.CharField(
        max_length=150
    )

    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.PROTECT
    )

    start_date = models.DateField()
    end_date = models.DateField()

    entry_test_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    entry_test_level = models.CharField(
        max_length=100,
        blank=True
    )

    exit_test_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    exit_test_level = models.CharField(
        max_length=100,
        blank=True
    )

    def clean(self):

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError({
                'end_date': (
                    "End date cannot be before the start date."
                )
            })

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"


class ClassSession(models.Model):

    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.PROTECT
    )

    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'class_group',
                    'date'
                ],
                name='unique_class_session_per_date'
            )
        ]

    def __str__(self):
        return f"{self.class_group.name} - {self.date}"


class Attendance(models.Model):

    STATUS_CHOICES = [
        ('P', 'Present'),
        ('A', 'Absent'),
        ('L', 'Leave'),
        ('H', 'Holiday'),
        ('C', 'Cancelled'),
    ]

    # Statuses a trainer sets per student.
    INDIVIDUAL_STATUSES = ('P', 'A', 'L')

    # Statuses a trainer sets for the whole class.
    CLASS_STATUSES = ('H', 'C')

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'student',
                    'session'
                ],
                name='unique_attendance_per_student_session'
            )
        ]

    def clean(self):

        if self.student_id and self.session_id:

            if (
                self.student.class_group
                != self.session.class_group
            ):
                raise ValidationError(
                    "The student's class group does not "
                    "match the session class group."
                )

            if (
                self.session.date
                < self.student.start_date
            ):
                raise ValidationError(
                    "Attendance cannot be recorded "
                    "before the student's start date."
                )

            if (
                self.session.date
                > self.student.end_date
            ):
                raise ValidationError(
                    "Attendance cannot be recorded "
                    "after the student's end date."
                )

    def __str__(self):
        return (
            f"{self.student.student_id} - "
            f"{self.session.date} - "
            f"{self.status}"
        )
