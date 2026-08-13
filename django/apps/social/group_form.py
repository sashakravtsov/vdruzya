"""Group create / edit / community post forms; forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.categories import CHOICES as GROUP_CATS
from apps.social.forms import ClassicForm, MultiFileField, _file, _files, _has_media, _in, _ta
from apps.social.models import Community, CommunityPost


class CreateGroupForm(ClassicForm, forms.Form):
    name = forms.CharField(max_length=255, widget=_in(style="width:100%"))
    category = forms.ChoiceField(choices=GROUP_CATS, widget=forms.Select())
    privacy = forms.ChoiceField(
        choices=[("public", "Открытая"), ("closed", "Закрытая")],
        initial="public",
        widget=forms.Select(),
    )
    short_description = forms.CharField(
        required=False, max_length=200,
        widget=_ta(2),
    )
    picture = forms.ImageField(required=False, label="Картинка", widget=_file())


class GroupForm(ClassicForm, forms.ModelForm):
    picture = forms.ImageField(required=False, label="Картинка", widget=_file())

    class Meta:
        model = Community
        fields = (
            "name", "slug", "category", "short_description", "description",
            "privacy", "join_mode", "posting_policy",
        )
        labels = {
            "slug": "Короткое имя",
            "short_description": "Последние новости",
            "posting_policy": "Кто пишет",
        }
        widgets = {
            "name": _in(style="width:100%"),
            "slug": _in(autocomplete="off"),
            "short_description": _ta(2, maxlength="200"),
            "description": _ta(4),
            "privacy": forms.Select(choices=[("public", "Открытая"), ("closed", "Закрытая")]),
            "join_mode": forms.Select(choices=[("open", "Свободный вход"), ("request", "По заявке")]),
            "posting_policy": forms.Select(choices=[
                ("members", "Только участники"), ("admins", "Только админы"),
            ]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"] = forms.ChoiceField(choices=GROUP_CATS, widget=forms.Select())
        for name in ("description", "short_description", "slug"):
            if name in self.fields:
                self.fields[name].required = False
        # Legacy "everyone" → members (FB 2006: members-only walls)
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "posting_policy", None) == "everyone":
            self.initial["posting_policy"] = "members"
            inst.posting_policy = "members"

    def clean_slug(self):
        from apps.social.slugs import clean_short_slug
        s = clean_short_slug(self.cleaned_data["slug"])
        qs = Community.objects.filter(slug=s)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Это короткое имя уже занято.")
        return s


class CommunityPostForm(ClassicForm, forms.ModelForm):
    subject = forms.CharField(
        required=False, max_length=120, label="Тема",
        widget=_in(style="width:100%"),
    )
    photo = MultiFileField(required=False, label="Фото / видео", widget=_files())
    board = forms.ChoiceField(
        choices=[("discussion", "Доска обсуждений"), ("wall", "Стена группы")],
        initial="discussion",
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = CommunityPost
        fields = ("body",)
        widgets = {"body": _ta(3)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False
        self.fields["body"].widget.attrs.update({
            "class": "inputtext msg-body-input",
            "spellcheck": "true",
            "maxlength": "4000",
            "placeholder": "Сообщение — можно Markdown",
            "rows": "5",
        })
        inst = getattr(self, "instance", None)
        if inst and inst.pk and (inst.topic or "") != "wall" and not self.is_bound:
            self.fields["subject"].initial = inst.subject
            self.fields["body"].initial = inst.body_text

    def clean(self):
        data = super().clean()
        board = data.get("board") or "discussion"
        body = (data.get("body") or "").strip()
        subject = (data.get("subject") or "").strip()
        has_media = _has_media(self) or bool(
            self.data.getlist("album_photo") if hasattr(self.data, "getlist") else []
        )
        if board == "discussion":
            if not subject:
                self.add_error("subject", "Укажите тему.")
            if not body and not has_media:
                self.add_error("body", "Напишите сообщение.")
        elif not body and not has_media:
            self.add_error("body", "Напишите текст или выберите фото / видео.")
        return data


