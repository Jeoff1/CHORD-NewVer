"""Shared view building blocks for every Module."""

from django.db.models import Q
from django.views.generic import ListView


class FilteredListView(ListView):
    """A paginated list with a search box (``?q=``).

    Set ``search_fields`` to the lookups to search, e.g.
    ``("first_name", "last_name")``. Templates include
    ``includes/list_toolbar.html`` and ``includes/pagination.html``.
    """

    paginate_by = 25
    search_fields = ()

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.get_search_query()
        if query and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(condition).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.get_search_query()
        return context


class FormPageMixin:
    """Renders a form view with the shared ``form_page.html`` layout.

    Set ``page_title``, and optionally ``submit_label``, ``intro``,
    ``cancel_url`` (or override ``get_cancel_url``) and ``get_links()``
    (related pages, as ``(label, url)`` pairs shown under the title).
    """

    template_name = "form_page.html"
    page_title = ""
    submit_label = "Save"
    intro = ""
    cancel_url = None

    def get_page_title(self):
        return self.page_title

    def get_cancel_url(self):
        return self.cancel_url

    def get_links(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            page_title=self.get_page_title(),
            submit_label=self.submit_label,
            intro=self.intro,
            cancel_url=self.get_cancel_url(),
            links=self.get_links(),
        )
        return context
