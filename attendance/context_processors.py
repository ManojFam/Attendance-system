from .permissions import is_report_viewer, is_trainer


def roles(request):
    """Lets templates show only the links a user is allowed to use."""
    user = getattr(request, 'user', None)

    if user is None or not user.is_authenticated:
        return {'user_is_trainer': False, 'user_is_report_viewer': False}

    return {
        'user_is_trainer': is_trainer(user),
        'user_is_report_viewer': is_report_viewer(user),
    }
