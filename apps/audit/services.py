"""Recording changes in the audit trail.

Typical use in a view (take the "before" snapshot when the form is built:
a ModelForm copies its data onto the instance while validating)::

    before = snapshot(obj, FIELDS)
    ...
    form.save()
    record_change(request.user, obj, AuditEvent.Action.CHANGED,
                  diff(before, snapshot(obj, FIELDS)))
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models.fields.files import FieldFile

from .models import AuditEvent


def display_value(value):
    """Turn a field value into a short string for the audit trail."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, models.Manager):  # a many-to-many field
        value = value.all()
    if isinstance(value, models.QuerySet | list | tuple | set):
        return ", ".join(sorted(str(v) for v in value))
    if isinstance(value, dict):
        return ", ".join(f"{k}: {display_value(v)}" for k, v in sorted(value.items()))
    if isinstance(value, FieldFile):
        return value.name or ""
    return str(value)


def snapshot(obj, fields):
    """Current display values of ``fields`` on ``obj``, keyed by field label.

    ``fields`` maps a label to an attribute name or to a callable taking
    ``obj``; a plain list of attribute names uses each model field's
    verbose name as the label.
    """
    if not isinstance(fields, dict):
        fields = {_label(obj, name): name for name in fields}
    values = {}
    for label, source in fields.items():
        value = source(obj) if callable(source) else getattr(obj, source)
        values[label] = display_value(value)
    return values


def diff(before, after):
    """``{label: [old, new]}`` for every value that changed.

    Pass ``{}`` as ``before`` for a new object and as ``after`` for a deleted
    one.
    """
    labels = [*after, *(label for label in before if label not in after)]
    return {
        label: [before.get(label, ""), after.get(label, "")]
        for label in labels
        if before.get(label, "") != after.get(label, "")
    }


def church_of(obj):
    """The church a record belongs to, or None (decision 0014): the church
    itself, its own ``church``, or its parent's through ``church_path``."""
    from apps.church.models import ChurchProfile

    if isinstance(obj, ChurchProfile):
        return obj
    path = getattr(obj, "church_path", None)
    if path is None:
        return getattr(obj, "church", None) if hasattr(obj, "church_id") else None
    for name in path.split("__"):
        obj = getattr(obj, name, None)
        if obj is None:
            return None
    return obj


def record_change(actor, obj, action, changes=None, *, church=None):
    """Write one audit event. Returns it, or None for a change with no edits.

    The event belongs to ``church``, else the record's own church, else the
    church the actor is working in (for records with none of their own,
    such as an account or a member)."""
    if action == AuditEvent.Action.CHANGED and not changes:
        return None
    church = church or church_of(obj) or getattr(actor, "current_church", None)
    return AuditEvent.objects.create(
        church=church,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
        object_repr=str(obj)[:200],
        changes=changes or {},
    )


def _label(obj, name):
    try:
        return str(obj._meta.get_field(name).verbose_name).capitalize()
    except FieldDoesNotExist:
        return name.replace("_", " ").capitalize()
