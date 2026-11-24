from .services import unread_count


def notifications(request):
    """Template context: the signed-in person's unread Notification count."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    return {"unread_notifications": unread_count(user)}
