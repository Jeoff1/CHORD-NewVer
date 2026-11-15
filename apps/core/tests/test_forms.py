from django import forms
from django.test import SimpleTestCase


class SampleForm(forms.Form):
    name = forms.CharField(help_text="Full name")
    color = forms.ChoiceField(choices=[("red", "Red"), ("blue", "Blue")])
    agree = forms.BooleanField(required=False)


class FormRenderingTests(SimpleTestCase):
    def test_widgets_get_bootstrap_classes(self):
        html = str(SampleForm())
        self.assertInHTML(
            '<input type="text" name="name" class="form-control" required '
            'id="id_name" aria-describedby="id_name_helptext">',
            html,
        )
        self.assertIn('class="form-select"', html)
        self.assertIn('class="form-check-input"', html)
        self.assertIn('class="form-text" id="id_name_helptext"', html)

    def test_invalid_field_is_marked(self):
        form = SampleForm(data={"color": "blue"})
        self.assertFalse(form.is_valid())
        html = str(form)
        self.assertIn('class="form-control is-invalid"', html)
        self.assertIn('class="invalid-feedback d-block"', html)

    def test_existing_widget_class_is_kept(self):
        class WideForm(forms.Form):
            note = forms.CharField(widget=forms.TextInput(attrs={"class": "w-50"}))

        self.assertIn('class="w-50 form-control"', str(WideForm()))
