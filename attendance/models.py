from django.db import models
from django.core.exceptions import ValidationError


class Course(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class ClassGroup(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} - {self.course.code}"


class Student(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=150)

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
                fields=['class_group', 'date'],
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
                fields=['student', 'session'],
                name='unique_attendance_per_student_session'
            )
        ]

    def clean(self):
        if self.student_id and self.session_id:

            if self.student.class_group != self.session.class_group:
                raise ValidationError(
                    "The student's class group does not match the session class group."
                )

            if self.session.date < self.student.start_date:
                raise ValidationError(
                    "Attendance cannot be recorded before the student's start date."
                )

            if self.session.date > self.student.end_date:
                raise ValidationError(
                    "Attendance cannot be recorded after the student's end date."
                )

    def __str__(self):
        return f"{self.student.student_id} - {self.session.date} - {self.status}"