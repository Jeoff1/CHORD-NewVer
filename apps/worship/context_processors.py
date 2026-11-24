from apps.church.modules import is_enabled


def occasions(request):
    """Template context: the number of Pending Occasion Requests, for
    people who may approve them, while Worship is switched on (Phase 9A,
    A5)."""
    user = getattr(request, "user", None)
    if not (
        user and user.is_authenticated and user.has_perm("worship.approve_occasion")
    ):
        return {}
    if not is_enabled("worship", getattr(request, "church", None)):
        return {}
    from .occasions import pending_count

    return {"pending_occasions": pending_count()}
