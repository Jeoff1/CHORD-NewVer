from apps.church.modules import is_enabled


def pending_requests(request):
    """Template context: how many Occasion Requests wait, for people who may
    approve them, while Occasions is switched on (Phase 9A, A5)."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    if not user.has_perm("occasions.approve_occasion"):
        return {}
    if not is_enabled("occasions", getattr(request, "church", None)):
        return {}
    from .rules import pending_count

    return {"pending_occasions": pending_count()}
