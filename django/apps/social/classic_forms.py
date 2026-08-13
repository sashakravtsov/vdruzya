"""Posted Items / Marketplace / Friend Lists forms — forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.forms import ClassicForm, _file, _in, _ta


class PostedItemForm(ClassicForm, forms.Form):
    """Links / Videos — URL and/or uploaded video file (classic Posted Items)."""
    title = forms.CharField(max_length=160, required=False, widget=_in(style="width:100%"))
    url = forms.CharField(max_length=500, required=False, widget=_in(style="width:100%"), label="Адрес")
    video = forms.FileField(
        required=False, label="Файл",
        widget=forms.FileInput(attrs={
            "class": "inputfile",
            "accept": "video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov",
        }),
    )
    blurb = forms.CharField(required=False, widget=_ta(3, style="width:100%"), label="Описание")
    visibility = forms.ChoiceField(
        choices=(("friends", "Друзья"), ("public", "Все")),
        widget=forms.Select(attrs={"class": "inputtext"}),
    )

    def __init__(self, *args, allow_upload=False, require_source=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_upload = allow_upload
        self.require_source = require_source
        if not allow_upload:
            self.fields.pop("video", None)

    def clean_url(self):
        from apps.social.classic_extra import normalize_url
        raw = (self.cleaned_data.get("url") or "").strip()
        if raw.startswith("storage:"):
            return raw[:500]
        return normalize_url(raw)

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]

    def clean(self):
        data = super().clean()
        if not self.require_source:
            return data
        url = data.get("url") or ""
        video = data.get("video") if self.allow_upload else None
        if self.allow_upload:
            if not url and not video:
                raise forms.ValidationError("Укажите ссылку или загрузите файл видео.")
        elif not url:
            self.add_error("url", "Укажите ссылку, например http://example.com")
        return data


class MarketForm(ClassicForm, forms.Form):
    title = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    price = forms.CharField(max_length=40, required=False, widget=_in(style="width:120px"))
    place = forms.CharField(
        max_length=120, required=False,
        widget=_in(
            style="width:100%", id="id_market_place",
            **{
                "data-osm-suggest": "1",
                "data-osm-lat": "#id_market_lat",
                "data-osm-lon": "#id_market_lon",
                "data-osm-fill": "keep",
                "autocomplete": "off",
            },
        ),
    )
    description = forms.CharField(required=False, widget=_ta(4, style="width:100%"))
    photo = forms.ImageField(required=False, label="Фото", widget=_file())
    lat = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_market_lat"}))
    lon = forms.FloatField(required=False, widget=forms.HiddenInput(attrs={"id": "id_market_lon"}))

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]


class FriendListForm(ClassicForm, forms.Form):
    name = forms.CharField(max_length=120, widget=_in(style="width:100%"))

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:120]


