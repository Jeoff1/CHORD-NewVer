"""Reading records of one church (decision 0014).

Every model whose records belong to a church reaches it through
``church_path``: ``"church"`` for a record that holds its church, or a path
through its parent for one that doesn't (a lineup is
``"service__church"``). Views read scoped records only through
``for_church`` and ``get_in_church``, so a record of another church is
never listed and opens as 404, never 403.
"""

from django.db import models
from django.shortcuts import get_object_or_404


class ChurchScopedQuerySet(models.QuerySet):
    """``Model.objects.for_church(church)``: only that church's records."""

    def for_church(self, church):
        return self.filter(**{self.model.church_path: church})


def church_scoped_manager(queryset_class=None):
    """A manager with ``for_church``, built on the model's own queryset
    class when it has one."""
    if queryset_class is None:
        return ChurchScopedQuerySet.as_manager()
    combined = type(
        f"Church{queryset_class.__name__}",
        (ChurchScopedQuerySet, queryset_class),
        {},
    )
    return combined.as_manager()


def get_in_church(queryset, church, **lookup):
    """The record matching ``lookup`` in ``church``, or 404 (also when it
    belongs to another church). ``queryset`` may be a model."""
    if isinstance(queryset, type):
        queryset = queryset._default_manager.all()
    return get_object_or_404(queryset.for_church(church), **lookup)


class ChurchScopedMixin:
    """View mixin: the view's records are the Current Church's only, so a
    record of another church is never listed and opens as 404."""

    def get_queryset(self):
        return super().get_queryset().for_church(self.request.church)


class ChurchFormKwargsMixin:
    """View mixin: gives the form ``church=request.church``."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["church"] = self.request.church
        return kwargs


class ChurchFormMixin:
    """Form mixin: takes ``church``, and puts it on a new record that
    belongs to a church. The church never comes from the form's data."""

    def __init__(self, *args, church, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "church_id", False) is None:
            instance.church = church
