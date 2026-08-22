from datetime import datetime

from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Student, ClassSession, Attendance, ClassGroup

@login_required
def trainer_attendance(request):

    selected_date_string = (
        request.GET.get('date')
        or request.POST.get('date')
    )

    selected_group_id = (
        request.GET.get('group')
        or request.POST.get('group')
    )

    if selected_date_string:
        selected_date = datetime.strptime(
            selected_date_string,
            '%Y-%m-%d'
        ).date()
    else:
        selected_date = timezone.localdate()

    class_groups = ClassGroup.objects.all()

    selected_group = None

    if selected_group_id:
        selected_group = ClassGroup.objects.filter(
            id=selected_group_id
        ).first()

    if not selected_group:
        selected_group = class_groups.first()

    students = Student.objects.none()
    session = None
    attendance_data = {}

    if selected_group:

        students = Student.objects.filter(
            class_group=selected_group,
            start_date__lte=selected_date,
            end_date__gte=selected_date
        )

        session = ClassSession.objects.filter(
            class_group=selected_group,
            date=selected_date
        ).first()

        if session:
            existing_attendance = Attendance.objects.filter(
                session=session,
                student__in=students
            )

            attendance_data = {
                record.student_id: record.status
                for record in existing_attendance
            }

    if request.method == 'POST':

        if session:

            for student in students:

                status = request.POST.get(
                    f'attendance_{student.id}'
                )

                if status:
                    Attendance.objects.update_or_create(
                        student=student,
                        session=session,
                        defaults={
                            'status': status
                        }
                    )

        return redirect(
            f'/trainer/?group={selected_group.id}&date={selected_date}'
        )

    for student in students:
        student.saved_status = attendance_data.get(student.id)

    context = {
        'students': students,
        'today': selected_date,
        'session': session,
        'class_groups': class_groups,
        'selected_group': selected_group,
    }

    return render(
        request,
        'attendance/trainer_attendance.html',
        context
    )