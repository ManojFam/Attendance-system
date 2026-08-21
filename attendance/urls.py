from django.urls import path
from . import views

urlpatterns = [
    path('trainer/', views.trainer_attendance, name='trainer_attendance'),
]