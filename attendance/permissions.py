from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


TRAINER_GROUP_NAME = 'Trainer'


def is_trainer(user):
    """Trainers mark attendance. Superusers may also use the trainer page."""
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name=TRAINER_GROUP_NAME).exists()
        )
    )


def is_report_viewer(user):
    """Admin staff (is_staff) can see attendance reports."""
    return user.is_authenticated and user.is_staff


def _role_required(check):
    """
    Anonymous users are sent to the login page.
    Logged-in users without the role get a clean 403 page instead of being
    bounced back to the login form (which is what user_passes_test does).
    """

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


trainer_required = _role_required(is_trainer)
report_viewer_required = _role_required(is_report_viewer)
