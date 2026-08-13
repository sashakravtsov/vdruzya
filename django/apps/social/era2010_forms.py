"""Places / Questions / Polls forms — forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.forms import ClassicForm, _file, _in, _ta


class PlaceForm(ClassicForm, forms.Form):
    name = forms.CharField(
        max_length=160,
        widget=_in(style="width:100%", **{
            "id": "id_place_name",
            "data-osm-suggest": "1",
            "data-osm-lat": "#id_place_lat",
            "data-osm-lon": "#id_place_lon",
            "data-osm-city": "#id_city",
            "data-osm-address": "#id_address",
            "data-osm-fill": "name",
            "autocomplete": "off",
        }),
    )
    city = forms.CharField(max_length=120, required=False, widget=_in(style="width:100%", id="id_city"))
    address = forms.CharField(max_length=255, required=False, widget=_in(style="width:100%", id="id_address"))
    photo = forms.ImageField(required=False, label="Фото", widget=_file())
    lat = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_place_lat"}))
    lon = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_place_lon"}))

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:160]


class CheckinForm(ClassicForm, forms.Form):
    message = forms.CharField(max_length=500, required=False, widget=_ta(2, style="width:100%"))
    photo = forms.ImageField(required=False, label="Фото", widget=_file())


class QuestionForm(ClassicForm, forms.Form):
    body = forms.CharField(max_length=500, widget=_ta(3, style="width:100%"))
    photo = forms.ImageField(required=False, label="Фото", widget=_file())

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите вопрос.")
        return body[:500]


class QuestionAnswerForm(ClassicForm, forms.Form):
    body = forms.CharField(max_length=500, widget=_ta(2, style="width:100%"))

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите ответ.")
        return body[:500]


class PlaceReviewForm(ClassicForm, forms.Form):
    stars = forms.TypedChoiceField(
        coerce=int,
        choices=[(i, f"{i}") for i in range(1, 6)],
        initial=5,
        widget=forms.Select(attrs={"class": "inputtext"}),
    )
    body = forms.CharField(max_length=500, required=False, widget=_ta(2, style="width:100%"))

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()[:500]


class PollForm(ClassicForm, forms.Form):
    question = forms.CharField(max_length=500, widget=_ta(2, style="width:100%"))
    options = forms.CharField(
        widget=_ta(4, style="width:100%"),
        help_text="По одному варианту на строку (минимум 2).",
    )

    def clean_question(self):
        q = (self.cleaned_data.get("question") or "").strip()
        if not q:
            raise forms.ValidationError("Напишите вопрос опроса.")
        return q[:500]

    def clean_options(self):
        raw = self.cleaned_data.get("options") or ""
        opts = []
        for line in raw.splitlines():
            body = line.strip()[:255]
            if body and body not in opts:
                opts.append(body)
        if len(opts) < 2:
            raise forms.ValidationError("Нужно минимум два варианта ответа.")
        return opts[:8]

