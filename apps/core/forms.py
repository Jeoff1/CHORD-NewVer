"""Project-wide form rendering: every form gets Bootstrap 5 markup.

``FORM_RENDERER`` points at ``ChordFormRenderer``, so forms need no styling
code of their own; ``{{ form }}`` renders Bootstrap fields with errors.
"""

from django.forms.boundfield import BoundField
from django.forms.renderers import DjangoTemplates

# Bootstrap class for each widget type (BoundField.widget_type); others get
# "form-control".
WIDGET_CLASSES = {
    "checkbox": "form-check-input",
    "radioselect": "form-check-input",
    "checkboxselectmultiple": "form-check-input",
    "select": "form-select",
    "selectmultiple": "form-select",
    "nullbooleanselect": "form-select",
}


class StyledBoundField(BoundField):
    """Adds Bootstrap classes, and ``is-invalid`` when the field has errors."""

    def build_widget_attrs(self, attrs, widget=None):
        attrs = super().build_widget_attrs(attrs, widget)
        widget = widget or self.field.widget
        classes = [
            widget.attrs.get("class", ""),
            attrs.get("class", ""),
            WIDGET_CLASSES.get(self.widget_type, "form-control"),
        ]
        if self.form.is_bound and self.errors:
            classes.append("is-invalid")
        attrs["class"] = " ".join(c for c in classes if c)
        return attrs


class ChordFormRenderer(DjangoTemplates):
    bound_field_class = StyledBoundField
    form_template_name = "core/forms/div.html"
    field_template_name = "core/forms/field.html"
