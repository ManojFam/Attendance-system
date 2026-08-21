from django.contrib import admin
from django.utils import timezone

from .models import (
    Course,
    ClassGroup,
    Student,
    ClassSession,
    Attendance,
)


admin.site.register(Course)
admin.site.register(ClassGroup)
admin.site.register(ClassSession)
admin.site.register(Attendance)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):

    list_display = (
        'student_id',
        'full_name',
        'class_group',
        'start_date',
        'end_date',
        'attendance_percentage',
        'entry_test_score',
        'entry_test_level',
        'exit_test_score',
        'exit_test_level',
    )

    search_fields = (
        'student_id',
        'full_name',
    )

    list_filter = (
        'class_group',
    )

    @admin.display(description='Attendance %')
    def attendance_percentage(self, obj):

        today = timezone.localdate()

        # Do not calculate beyond the student's end date
        calculation_end_date = min(today, obj.end_date)

        # Student has not started yet
        if calculation_end_date < obj.start_date:
            return "0.00%"

        # All scheduled sessions for this student's group
        sessions = ClassSession.objects.filter(
            class_group=obj.class_group,
            date__gte=obj.start_date,
            date__lte=calculation_end_date
        )

        total_sessions = sessions.count()

        attendance_records = Attendance.objects.filter(
            student=obj,
            session__in=sessions
        )

        present = attendance_records.filter(status='P').count()
        holidays = attendance_records.filter(status='H').count()
        cancelled = attendance_records.filter(status='C').count()

        eligible_sessions = total_sessions - holidays - cancelled

        if eligible_sessions <= 0:
            return "0.00%"

        percentage = (present / eligible_sessions) * 100

        return f"{percentage:.2f}%"