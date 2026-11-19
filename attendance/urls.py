from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('trainer/', views.trainer_attendance, name='trainer_attendance'),
    path('reports/', views.attendance_report, name='attendance_report'),
    path(
        'reports/export.csv',
        views.attendance_report_csv,
        name='attendance_report_csv'
    ),
    path(
        'reports/student/<int:pk>/',
        views.student_detail,
        name='student_detail'
    ),
]
