from django.contrib import admin
from django.utils import timezone

from .models import (
    Course,
    ClassGroup,
    Student,
    ClassSession,
    Attendance,
)


class StudentStatusFilter(admin.SimpleListFilter):
    title = 'student status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active'),
            ('not_started', 'Not Started'),
            ('completed', 'Completed'),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()

        if self.value() == 'active':
            return queryset.filter(
                start_date__lte=today,
                end_date__gte=today
            )

        if self.value() == 'not_started':
            return queryset.filter(
                start_date__gt=today
            )

        if self.value() == 'completed':
            return queryset.filter(
                end_date__lt=today
            )

        return queryset


admin.site.register(Course)
admin.site.register(ClassGroup)


class AttendanceInline(admin.TabularInline):
    model = Attendance

    extra = 0

    readonly_fields = (
        'session',
        'status',
    )

    can_delete = False


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):

    list_display = (
        'student_id',
        'full_name',
        'class_group',
        'start_date',
        'end_date',
        'student_status',
        'attendance_percentage',
        'entry_test_score',
        'entry_test_level',
        'exit_test_score',
        'exit_test_level',
    )

    readonly_fields = (
        'attendance_percentage',
    )

    search_fields = (
        'student_id',
        'full_name',
    )

    list_filter = (
        'class_group',
        StudentStatusFilter,
    )

    inlines = [
        AttendanceInline,
    ]

    @admin.display(description='Status')
    def student_status(self, obj):

        if not obj or not obj.start_date or not obj.end_date:
            return "—"

        today = timezone.localdate()

        if today < obj.start_date:
            return "Not Started"

        if today > obj.end_date:
            return "Completed"

        return "Active"

    @admin.display(description='Attendance %')
    def attendance_percentage(self, obj):

        # A new student has not been saved yet,
        # so the required fields may still be empty.
        if (
            not obj
            or not obj.start_date
            or not obj.end_date
            or not obj.class_group_id
        ):
            return "—"

        today = timezone.localdate()

        calculation_end_date = min(
            today,
            obj.end_date
        )

        # Student has not started yet.
        if calculation_end_date < obj.start_date:
            return "0.00%"

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

        present = attendance_records.filter(
            status='P'
        ).count()

        holidays = attendance_records.filter(
            status='H'
        ).count()

        cancelled = attendance_records.filter(
            status='C'
        ).count()

        eligible_sessions = (
            total_sessions
            - holidays
            - cancelled
        )

        if eligible_sessions <= 0:
            return "0.00%"

        percentage = (
            present / eligible_sessions
        ) * 100

        return f"{percentage:.2f}%"