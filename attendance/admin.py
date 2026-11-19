from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Course,
    ClassGroup,
    Student,
    Attendance,
)
from .services import attendance_summary, student_status


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


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


class ClassGroupAdminForm(forms.ModelForm):
    """
    Adds the JavaScript that limits how many weekday boxes can be ticked.
    The real rule is still enforced by ClassGroup.clean().
    """

    class Meta:
        model = ClassGroup
        fields = '__all__'

    class Media:
        js = ('attendance/admin/class_days_limit.js',)
        css = {'all': ('attendance/admin/class_days_limit.css',)}


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    form = ClassGroupAdminForm

    list_display = (
        'name',
        'course',
        'class_days_per_week',
        'schedule',
    )

    list_filter = ('course',)
    list_select_related = ('course',)
    search_fields = ('name', 'course__code', 'course__name')

    fieldsets = (
        (None, {
            'fields': ('name', 'course'),
        }),
        ('Teaching schedule', {
            'description': (
                'Pick how many days per week this class runs, then tick '
                'exactly that many weekdays. Saving a changed schedule '
                'updates future sessions only; past sessions and any '
                'session with attendance are kept.'
            ),
            'fields': (
                'class_days_per_week',
                (
                    'monday',
                    'tuesday',
                    'wednesday',
                    'thursday',
                    'friday',
                    'saturday',
                    'sunday',
                ),
            ),
        }),
    )

    @admin.display(description='Class days')
    def schedule(self, obj):
        return obj.schedule_display()


class AttendanceInline(admin.TabularInline):
    model = Attendance

    extra = 0

    readonly_fields = (
        'session',
        'status',
    )

    can_delete = False

    def has_add_permission(self, request, obj=None):
        # Attendance is entered by trainers on the trainer page.
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('session__class_group')
            .order_by('-session__date')
        )


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
        'unmarked_sessions',
        'entry_test_score',
        'entry_test_level',
        'exit_test_score',
        'exit_test_level',
        'report_link',
    )

    list_select_related = (
        'class_group__course',
    )

    readonly_fields = (
        'attendance_percentage',
        'unmarked_sessions',
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

    @staticmethod
    def _has_required_fields(obj):
        # A new student has not been saved yet,
        # so the required fields may still be empty.
        # Keep this check: without it the Add page crashes.
        return bool(
            obj
            and obj.start_date
            and obj.end_date
            and obj.class_group_id
        )

    @admin.display(description='Status')
    def student_status(self, obj):

        if not obj or not obj.start_date or not obj.end_date:
            return "—"

        return student_status(obj)

    @admin.display(description='Attendance %')
    def attendance_percentage(self, obj):

        if not self._has_required_fields(obj):
            return "—"

        return attendance_summary(obj).percentage_display

    @admin.display(description='Unmarked')
    def unmarked_sessions(self, obj):
        """Past sessions with no attendance entered yet."""

        if not self._has_required_fields(obj):
            return "—"

        return attendance_summary(obj).unmarked

    @admin.display(description='Report')
    def report_link(self, obj):
        return format_html(
            '<a href="{}">View</a>',
            reverse('student_detail', args=[obj.pk]),
        )
