"""Page create / wall post forms — forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.forms import ClassicForm, MultiFileField, _file, _files, _in, _ta


class PageForm(ClassicForm, forms.Form):
    """Create / edit a public Page (Страница)."""
    name = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    industry = forms.ChoiceField(choices=[], widget=forms.Select())
    city = forms.CharField(max_length=120, required=False, widget=_in(style="width:100%"))
    description = forms.CharField(required=False, widget=_ta(4, style="width:100%"))
    cover = forms.ImageField(required=False, label="Обложка", widget=_file())

    def __init__(self, *args, **kwargs):
        from apps.social.page_categories import CHOICES
        super().__init__(*args, **kwargs)
        self.fields["industry"].choices = CHOICES

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:160]

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()[:120]

    def clean_description(self):
        return (self.cleaned_data.get("description") or "").strip()


class PagePostForm(ClassicForm, forms.Form):
    """Admin update on a Page wall."""
    body = forms.CharField(required=False, widget=_ta(3, style="width:100%"))
    photo = MultiFileField(required=False, label="Фото / видео", widget=_files())

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not self.files.get("photo"):
            self.add_error("body", "Напишите текст или выберите фото / видео.")
        return data


