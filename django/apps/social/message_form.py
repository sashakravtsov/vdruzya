"""Inbox compose forms — forms re-exports."""
from __future__ import annotations

from django import forms

from apps.social.forms import ClassicForm, _in, _media_file, _ta
from apps.social.models import Message


class MessageForm(ClassicForm, forms.ModelForm):
    photo = forms.FileField(required=False, label="Фото / видео", widget=_media_file())
    voice = forms.FileField(
        required=False, label="Голосовое",
        widget=forms.FileInput(attrs={
            "class": "inputfile",
            "accept": "audio/*,audio/webm,audio/ogg,audio/mp4,.webm,.ogg,.mp3,.m4a,.wav",
            "id": "id_voice_file",
        }),
    )
    waveform = forms.CharField(required=False, max_length=512, widget=forms.HiddenInput(attrs={"id": "id_voice_wave"}))
    duration_ms = forms.IntegerField(required=False, widget=forms.HiddenInput(attrs={"id": "id_voice_ms"}))
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput())
    sticker = forms.ChoiceField(required=False, choices=(), widget=forms.Select(attrs={"class": "inputtext"}))

    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": _ta(6, style="width:100%")}

    def __init__(self, *args, stickers=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "— без стикера —")]
        for s in stickers or []:
            choices.append((str(s.id), s.title))
        self.fields["sticker"].choices = choices
        # Visual picker in Inbox; keep value as hidden field
        if stickers:
            self.fields["sticker"].widget = forms.HiddenInput(attrs={"id": "id_sticker"})
            self.fields["body"].widget.attrs.setdefault("id", "id_message_body")
            self.fields["body"].widget.attrs.update({
                "class": "inputtext msg-body-input",
                "spellcheck": "true",
                "maxlength": "4000",
                "placeholder": "Сообщение — можно Markdown",
            })

    def clean(self):
        data = super().clean()
        if (
            not (data.get("body") or "").strip()
            and not self.files.get("photo")
            and not self.files.get("voice")
            and not data.get("sticker")
        ):
            self.add_error("body", "Напишите текст, приложите фото / видео / голосовое или выберите стикер.")
        return data


class ComposeMessageForm(ClassicForm, forms.Form):
    to = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": "inputtext", "style": "width:100%;max-width:420px"}),
    )
    subject = forms.CharField(
        required=False, max_length=160, label="Тема",
        widget=_in(style="width:100%"),
    )
    body = forms.CharField(
        required=False,
        widget=_ta(6, style="width:100%"),
    )
    photo = forms.FileField(required=False, label="Фото / видео", widget=_media_file())
    sticker = forms.ChoiceField(required=False, choices=(), widget=forms.Select(attrs={"class": "inputtext"}))

    def __init__(self, friends, *args, stickers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to"].choices = [("", "— выберите друга —")] + [(str(p.id), p.name) for p in friends]
        choices = [("", "— без стикера —")]
        for s in stickers or []:
            choices.append((str(s.id), s.title))
        self.fields["sticker"].choices = choices
        if stickers:
            self.fields["sticker"].widget = forms.HiddenInput(attrs={"id": "id_compose_sticker"})
            self.fields["body"].widget.attrs.setdefault("id", "id_compose_body")
            self.fields["body"].widget.attrs.update({
                "class": "inputtext msg-body-input",
                "spellcheck": "true",
                "maxlength": "4000",
                "placeholder": "Сообщение — можно Markdown",
            })

    def clean(self):
        data = super().clean()
        if not data.get("to"):
            self.add_error("to", "Выберите друга.")
        if (
            not (data.get("body") or "").strip()
            and not self.files.get("photo")
            and not data.get("sticker")
        ):
            self.add_error("body", "Напишите текст, приложите фото / видео или выберите стикер.")
        return data


