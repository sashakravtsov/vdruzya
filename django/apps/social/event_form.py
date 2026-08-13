"""Event + Gift send forms — forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.forms import ClassicForm, _file, _in, _ta
from apps.social.models import SocialProfile


class EventForm(ClassicForm, forms.Form):
    """Classic Events create — text date, no datetime-local (+ optional cover)."""
    title = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    place = forms.CharField(
        max_length=160, required=False,
        widget=_in(
            style="width:100%", id="id_event_place",
            **{
                "data-osm-suggest": "1",
                "data-osm-lat": "#id_event_lat",
                "data-osm-lon": "#id_event_lon",
                "data-osm-fill": "keep",
                "autocomplete": "off",
            },
        ),
    )
    starts_at = forms.CharField(
        max_length=32,
        widget=_in(style="width:160px"),
        help_text="ДД.ММ.ГГГГ ЧЧ:ММ",
    )
    description = forms.CharField(required=False, widget=_ta(3, style="width:100%"))
    cover = forms.ImageField(required=False, label="Обложка", widget=_file())
    lat = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_event_lat"}))
    lon = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_event_lon"}))

    def clean_starts_at(self):
        from apps.social.events import parse_starts
        starts = parse_starts(self.cleaned_data.get("starts_at"))
        if not starts:
            raise forms.ValidationError("Укажите дату, например 15.09.2006 19:00")
        return starts

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]

    def clean_place(self):
        return (self.cleaned_data.get("place") or "").strip()[:160]


class GiftSendForm(ClassicForm, forms.Form):
    """Send a classic Gift (sticker) to a friend."""
    to = forms.ModelChoiceField(
        queryset=SocialProfile.objects.none(),
        empty_label="— выберите друга —",
        widget=forms.Select(attrs={"class": "inputtext"}),
    )
    gift = forms.CharField(max_length=80, widget=forms.HiddenInput())
    message = forms.CharField(
        max_length=500, required=False,
        widget=_ta(2, style="width:100%"),
    )

    def clean_gift(self):
        slug = (self.cleaned_data.get("gift") or "").strip()
        if not slug:
            raise forms.ValidationError("Выберите подарок")
        return slug



