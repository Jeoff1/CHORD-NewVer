from apps.church.modules import is_enabled

from .notifying import unread_count


def notifications(request):
    """Template context: the signed-in person's unread Notification count,
    while Teams is switched on."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    if not is_enabled("teams", getattr(request, "church", None)):
        return {}
    return {"unread_notifications": unread_count(user)}
