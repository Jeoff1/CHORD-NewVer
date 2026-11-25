"""Church-edited lists: small lists each church defines for itself.

Examples: Membership Statuses, relationship types, and later Event Types,
Funds and Payment Methods. A Module defines a model on ``ChoiceItem`` (or any
model) and gets list, add and edit pages from ``setting_list_urls``. Items
are switched off rather than deleted, so records that use them keep them;
the list's Active column is a switch for people who may change items.
"""

from dataclasses import dataclass, field

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import models
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.views.generic import CreateView, ListView, UpdateView, View

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import is_enabled

from .models import TimeStampedModel
from .views import FormPageMixin


class ChoiceItemQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def usable(self, current=None):
        """Active items, plus ``current`` so editing a record keeps its value."""
        condition = models.Q(is_active=True)
        if current is not None:
            condition |= models.Q(pk=getattr(current, "pk", current))
        return self.filter(condition)


class ChoiceItem(TimeStampedModel):
    """One entry of a church-edited list."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=250, blank=True)
    sort_order = models.PositiveSmallIntegerField(
        default=0, help_text="Lower numbers come first."
    )
    is_active = models.BooleanField(
        "Active",
        default=True,
        help_text="Inactive items stay on existing records but can't be "
        "chosen for new ones.",
    )

    objects = ChoiceItemQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]
        default_permissions = ("add", "change", "view")

    def __str__(self):
        return self.name


@dataclass
class SettingList:
    """How one church-edited list appears.

    ``columns`` are ``(header, attribute)`` pairs shown in the list;
    ``nav`` is an optional ``callable(request) -> [(label, url)]`` that
    links the list to its sibling settings pages. ``title`` may be a
    ``callable(request) -> str`` when it uses one of the church's Labels.
    """

    model: type
    url_prefix: str
    title: object
    item_name: str
    intro: str = ""
    module: str | None = None
    fields: list = field(
        default_factory=lambda: ["name", "description", "sort_order", "is_active"]
    )
    form_class: type | None = None
    columns: list = field(
        default_factory=lambda: [
            ("Name", "name"),
            ("Description", "description"),
            ("Order", "sort_order"),
            ("Active", "is_active"),
        ]
    )
    nav: object = None

    def permission(self, action):
        opts = self.model._meta
        return f"{opts.app_label}.{action}_{opts.model_name}"

    def get_form_class(self):
        return self.form_class or modelform_factory(self.model, fields=self.fields)

    def get_title(self, request):
        return self.title(request) if callable(self.title) else self.title

    def audit_fields(self):
        """The form's fields, labelled by their verbose names."""
        return {
            str(self.model._meta.get_field(name).verbose_name).capitalize(): name
            for name in self.fields
        }

    @property
    def can_switch(self):
        """Whether items can be switched on and off from the list."""
        return "is_active" in self.fields


class SettingListMixin(LoginRequiredMixin, PermissionRequiredMixin):
    setting_list: SettingList = None
    action = "view"

    def dispatch(self, request, *args, **kwargs):
        module = self.setting_list.module
        if module and not is_enabled(module, getattr(request, "church", None)):
            raise Http404("This module is switched off.")
        return super().dispatch(request, *args, **kwargs)

    def get_permission_required(self):
        return [self.setting_list.permission(self.action)]

    def url(self, name, **kwargs):
        namespace = self.request.resolver_match.namespace
        prefix = self.setting_list.url_prefix
        return reverse(f"{namespace}:{prefix}_{name}", kwargs=kwargs)

    def nav_links(self):
        nav = self.setting_list.nav
        return nav(self.request) if nav else []


class SettingListView(SettingListMixin, ListView):
    template_name = "core/setting_list.html"

    def get_queryset(self):
        return self.setting_list.model.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = self.setting_list
        can_add = self.request.user.has_perm(config.permission("add"))
        can_change = self.request.user.has_perm(config.permission("change"))
        context.update(
            config=config,
            title=config.get_title(self.request),
            nav_links=self.nav_links(),
            current_url=self.request.path,
            create_url=self.url("create") if can_add else None,
            rows=[
                (
                    item,
                    [
                        self._cell(item, attribute, can_change)
                        for _, attribute in config.columns
                    ],
                    self.url("update", pk=item.pk) if can_change else None,
                )
                for item in context["object_list"]
            ],
        )
        return context

    def _cell(self, item, attribute, can_change):
        """``(value, switch_url)``: the Active column of a list whose items
        can be switched gets a switch for people who may change them."""
        switch = (
            attribute == "is_active" and can_change and self.setting_list.can_switch
        )
        return (
            self._value(item, attribute),
            self.url("switch", pk=item.pk) if switch else None,
        )

    @staticmethod
    def _value(item, attribute):
        if callable(attribute):
            return attribute(item)
        display = getattr(item, f"get_{attribute}_display", None)
        return display() if display else getattr(item, attribute)


class SettingSwitchView(SettingListMixin, View):
    """Switches one item on or off from the list (POST only).

    The post carries the state wanted (``is_active`` present means on), so
    a page left open, or a second click, never flips an item the wrong way.
    """

    action = "change"
    template_name = "core/includes/active_switch.html"

    def post(self, request, pk):
        config = self.setting_list
        if not config.can_switch:
            raise Http404("This list has no Active switch.")
        item = get_object_or_404(config.model, pk=pk)
        fields = {"Active": "is_active"}
        before = snapshot(item, fields)
        wanted = "is_active" in request.POST
        if item.is_active == wanted:
            return self._respond(request, item)
        item.is_active = wanted
        item.save(
            update_fields=[
                name for name in ("is_active", "updated_at") if hasattr(item, name)
            ]
        )
        record_change(
            request.user,
            item,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(item, fields)),
        )
        return self._respond(request, item)

    def _respond(self, request, item):
        if request.headers.get("HX-Request"):
            return render(
                request,
                self.template_name,
                {"item": item, "value": item.is_active, "switch_url": request.path},
            )
        return redirect(self.url("list"))


class _SettingFormView(SettingListMixin, FormPageMixin):
    def get_form_class(self):
        return self.setting_list.get_form_class()

    def get_success_url(self):
        return self.url("list")

    def get_cancel_url(self):
        return self.url("list")

    def get_links(self):
        # The Settings hub's menu links the other settings pages.
        return []

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            self.audit_action,
            diff(self.before, snapshot(self.object, self.setting_list.audit_fields())),
        )
        return response


class SettingCreateView(_SettingFormView, CreateView):
    action = "add"
    audit_action = AuditEvent.Action.CREATED
    before = {}

    def get_page_title(self):
        return f"Add {self.setting_list.item_name.lower()}"


class SettingUpdateView(_SettingFormView, UpdateView):
    action = "change"
    audit_action = AuditEvent.Action.CHANGED

    def get_queryset(self):
        return self.setting_list.model.objects.all()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, self.setting_list.audit_fields())
        return kwargs

    def get_page_title(self):
        return f"Edit {self.setting_list.item_name.lower()}: {self.object}"


def setting_list_urls(config: SettingList, route_prefix=""):
    """List, add, edit and switch URLs for one church-edited list, named
    ``<url_prefix>_list``, ``_create``, ``_update`` and ``_switch``, under
    ``<route_prefix><url-prefix>/``."""
    prefix = config.url_prefix
    route = route_prefix + prefix.replace("_", "-")
    return [
        path(
            f"{route}/",
            SettingListView.as_view(setting_list=config),
            name=f"{prefix}_list",
        ),
        path(
            f"{route}/new/",
            SettingCreateView.as_view(setting_list=config),
            name=f"{prefix}_create",
        ),
        path(
            f"{route}/<int:pk>/",
            SettingUpdateView.as_view(setting_list=config),
            name=f"{prefix}_update",
        ),
        path(
            f"{route}/<int:pk>/switch/",
            SettingSwitchView.as_view(setting_list=config),
            name=f"{prefix}_switch",
        ),
    ]
