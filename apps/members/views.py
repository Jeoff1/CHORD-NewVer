from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import ModuleRequiredMixin
from apps.core.custom_fields import custom_values
from apps.core.storage import private_file_response
from apps.core.views import FilteredListView, FormPageMixin

from . import services
from .forms import HouseholdForm, ImportUploadForm, MemberForm
from .models import Household, Member, MemberField, MembershipStatus

PRIVATE_PERMISSION = "members.view_private_details"
IMPORT_SESSION_KEY = "members_import"
HOUSEHOLD_AUDIT_FIELDS = {"Name": "name", "Notes": "notes"}


def can_view_private(user):
    return user.has_perm(PRIVATE_PERMISSION)


class MembersMixin(ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin):
    module = "members"


class MemberObjectMixin:
    """Looks members up by their public ID."""

    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    model = Member


# --- Members -----------------------------------------------------------------


class MemberListView(MembersMixin, FilteredListView):
    permission_required = "members.view_member"
    model = Member
    template_name = "members/member_list.html"
    SHOW = {"current": "Current", "archived": "Archived", "all": "All"}

    @property
    def search_fields(self):
        fields = ("first_name", "middle_name", "last_name", "suffix")
        if can_view_private(self.request.user):
            fields += ("email", "phone")
        return fields

    def get_show(self):
        show = self.request.GET.get("show", "current")
        return show if show in self.SHOW else "current"

    def get_status(self):
        status = self.request.GET.get("status", "")
        return int(status) if status.isdigit() else None

    def get_queryset(self):
        queryset = (
            super().get_queryset().select_related("status", "household", "relationship")
        )
        show = self.get_show()
        if show == "current":
            queryset = queryset.current()
        elif show == "archived":
            queryset = queryset.archived()
        if self.get_status():
            queryset = queryset.filter(status_id=self.get_status())
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            show=self.get_show(),
            show_choices=self.SHOW.items(),
            status_filter=self.get_status(),
            statuses=MembershipStatus.objects.all(),
            private=can_view_private(user),
            can_settings=any(
                user.has_perm(p)
                for p in (
                    "members.view_membershipstatus",
                    "members.view_relationshiptype",
                    "members.view_memberfield",
                )
            ),
        )
        return context


class MemberExportView(MemberListView):
    permission_required = "members.export_member"
    paginate_by = None

    def get(self, request, *args, **kwargs):
        content = services.export_csv(
            self.get_queryset(), include_private=can_view_private(request.user)
        )
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="members.csv"'
        return response


def member_detail_context(member, user, *, own_record=False):
    private = own_record or can_view_private(user)
    context = {
        "member": member,
        "private": private,
        "own_record": own_record,
        "custom_values": custom_values(
            MemberField.objects.all(), member.custom_data, include_private=private
        ),
        "household_members": (
            member.household.members.current()
            .exclude(pk=member.pk)
            .select_related("relationship")
            if member.household
            else []
        ),
    }
    if not own_record and user.has_perm("audit.view_auditevent"):
        context["history"] = AuditEvent.objects.filter(
            content_type=ContentType.objects.get_for_model(Member),
            object_id=str(member.pk),
        ).select_related("actor")[:10]
    return context


class MemberDetailView(MembersMixin, MemberObjectMixin, DetailView):
    permission_required = "members.view_member"
    template_name = "members/member_detail.html"

    def get_queryset(self):
        return Member.objects.select_related("status", "household", "relationship")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(member_detail_context(self.object, self.request.user))
        return context


class MyRecordView(ModuleRequiredMixin, LoginRequiredMixin, View):
    """The signed-in person's own member record, if their account is linked."""

    module = "members"

    def get(self, request):
        member = Member.objects.filter(user=request.user).first()
        if member is None:
            return self._render(request, {"member": None})
        return self._render(
            request, member_detail_context(member, request.user, own_record=True)
        )

    def _render(self, request, context):
        return render(request, "members/member_detail.html", context)


class MemberFormMixin(MembersMixin, FormPageMixin):
    model = Member
    form_class = MemberForm
    template_name = "members/member_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["can_view_private"] = can_view_private(self.request.user)
        return kwargs

    def get_success_url(self):
        return reverse("members:detail", kwargs={"public_id": self.object.public_id})


class MemberCreateView(MemberFormMixin, CreateView):
    permission_required = "members.add_member"
    cancel_url = reverse_lazy("members:list")

    def get_page_title(self):
        return f"Add {self.request.church.label_set.get('member').lower()}"

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, services.member_audit_fields())),
        )
        messages.success(self.request, f"{self.object} was added.")
        return response


class MemberUpdateView(MemberObjectMixin, MemberFormMixin, UpdateView):
    permission_required = "members.change_member"

    def get_page_title(self):
        return f"Edit {self.object}"

    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, services.member_audit_fields())
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, services.member_audit_fields())),
        )
        messages.success(self.request, f"{self.object} was saved.")
        return response


class MemberArchiveView(MembersMixin, MemberObjectMixin, View):
    """POST ``archive=1`` to archive, ``archive=0`` to restore."""

    permission_required = "members.change_member"

    def post(self, request, public_id):
        member = get_object_or_404(Member, public_id=public_id)
        archive = request.POST.get("archive") == "1"
        services.set_archived(member, archive, request.user)
        verb = "archived" if archive else "restored"
        messages.success(request, f"{member} was {verb}.")
        return redirect("members:detail", public_id=member.public_id)


class MemberPhotoView(MembersMixin, View):
    permission_required = "members.view_member"

    def get(self, request, public_id):
        member = get_object_or_404(Member, public_id=public_id)
        return private_file_response(member.photo.name, inline=True)


class MemberFileView(MembersMixin, View):
    permission_required = "members.view_member"

    def get(self, request, public_id, key):
        member = get_object_or_404(Member, public_id=public_id)
        definition = get_object_or_404(MemberField, key=key)
        if definition.is_private and not can_view_private(request.user):
            raise PermissionDenied
        name = (member.custom_data or {}).get(definition.key)
        if not isinstance(name, str):
            raise Http404("No file.")
        return private_file_response(name)


class MyFileView(ModuleRequiredMixin, LoginRequiredMixin, View):
    """Files on the signed-in person's own record."""

    module = "members"

    def get(self, request, kind, key=""):
        member = get_object_or_404(Member, user=request.user)
        if kind == "photo":
            return private_file_response(member.photo.name, inline=True)
        definition = get_object_or_404(MemberField, key=key)
        name = (member.custom_data or {}).get(definition.key)
        if not isinstance(name, str):
            raise Http404("No file.")
        return private_file_response(name)


# --- Import ------------------------------------------------------------------


class ImportMixin(MembersMixin):
    permission_required = "members.import_member"

    def include_private(self):
        return can_view_private(self.request.user)

    def stored_check(self):
        stored = self.request.session.get(IMPORT_SESSION_KEY)
        if not stored:
            return None
        return services.check_import(
            stored["headers"], stored["rows"], include_private=self.include_private()
        )


class ImportUploadView(ImportMixin, FormView):
    form_class = ImportUploadForm
    template_name = "members/import_upload.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["columns"] = services.columns(include_private=self.include_private())
        return context

    def form_valid(self, form):
        try:
            headers, rows = services.read_csv(form.cleaned_data["file"])
        except services.ImportFileError as error:
            form.add_error("file", str(error))
            return self.form_invalid(form)
        self.request.session[IMPORT_SESSION_KEY] = {
            "file_name": form.cleaned_data["file"].name,
            "headers": headers,
            "rows": rows,
        }
        return redirect("members:import_preview")


class ImportPreviewView(ImportMixin, View):
    PREVIEW_ROWS = 20

    def get(self, request):
        check = self.stored_check()
        if check is None:
            return redirect("members:import")
        return render(
            request,
            "members/import_preview.html",
            {
                "check": check,
                "file_name": request.session[IMPORT_SESSION_KEY]["file_name"],
                "preview_rows": check.ready[: self.PREVIEW_ROWS],
                "more_ready": max(len(check.ready) - self.PREVIEW_ROWS, 0),
            },
        )

    def post(self, request):
        check = self.stored_check()
        if check is None:
            return redirect("members:import")
        if check.missing_columns:
            messages.error(request, "The file is missing required columns.")
            return redirect("members:import_preview")
        count = services.import_members(check, request.user)
        skipped = len(check.with_problems)
        request.session.pop(IMPORT_SESSION_KEY, None)
        text = f"Imported {count} {'person' if count == 1 else 'people'}."
        if skipped:
            text += f" {skipped} row{'s' if skipped != 1 else ''} with problems "
            text += "were skipped."
        messages.success(request, text)
        return redirect("members:list")


class ImportProblemsView(ImportMixin, View):
    def get(self, request):
        check = self.stored_check()
        if check is None:
            return redirect("members:import")
        response = HttpResponse(
            services.problems_csv(check), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            'attachment; filename="members-not-imported.csv"'
        )
        return response


class ImportTemplateView(ImportMixin, View):
    def get(self, request):
        response = HttpResponse(
            services.template_csv(include_private=self.include_private()),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="members-template.csv"'
        return response


class ImportCancelView(ImportMixin, View):
    def post(self, request):
        request.session.pop(IMPORT_SESSION_KEY, None)
        return redirect("members:import")


# --- Households --------------------------------------------------------------


class HouseholdListView(MembersMixin, FilteredListView):
    permission_required = "members.view_household"
    model = Household
    template_name = "members/household_list.html"
    search_fields = ("name",)

    def get_queryset(self):
        # Counting drops the model's default ordering, so order explicitly.
        return (
            super()
            .get_queryset()
            .annotate(
                member_count=Count(
                    "members", filter=Q(members__archived_at__isnull=True)
                )
            )
            .order_by("name")
        )


class HouseholdDetailView(MembersMixin, DetailView):
    permission_required = "members.view_household"
    model = Household
    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    template_name = "members/household_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["people"] = self.object.members.select_related(
            "relationship", "status"
        ).order_by("relationship__sort_order", "birth_date", "first_name")
        return context


class HouseholdFormMixin(MembersMixin, FormPageMixin):
    model = Household
    form_class = HouseholdForm

    def get_success_url(self):
        return reverse(
            "members:household_detail", kwargs={"public_id": self.object.public_id}
        )


class HouseholdCreateView(HouseholdFormMixin, CreateView):
    permission_required = "members.add_household"
    page_title = "Add household"
    intro = "After adding the household, add people to it from their member pages."
    cancel_url = reverse_lazy("members:household_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, HOUSEHOLD_AUDIT_FIELDS)),
        )
        return response


class HouseholdUpdateView(HouseholdFormMixin, UpdateView):
    permission_required = "members.change_household"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_page_title(self):
        return f"Edit household: {self.object}"

    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, HOUSEHOLD_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, HOUSEHOLD_AUDIT_FIELDS)),
        )
        return response
