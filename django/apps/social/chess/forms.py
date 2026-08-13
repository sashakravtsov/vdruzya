"""Django forms for the Chess canvas (classic chrome widgets)."""
from __future__ import annotations

import re

from django import forms

from apps.social.forms import ClassicForm

_SQ = re.compile(r"^[a-hA-H][1-8]$")


def _sel(**extra):
    return forms.Select(attrs={"class": "inputtext", **extra})


def _txt(size=4, **extra):
    return forms.TextInput(attrs={"class": "inputtext", "size": str(size), **extra})


class SquareField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 2)
        kwargs.setdefault("widget", _txt(4, maxlength="2", autocomplete="off"))
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        value = (value or "").strip().lower()
        if not _SQ.match(value):
            raise forms.ValidationError("Клетка должна быть вида e2 или h7")
        return value


class StartGameForm(ClassicForm, forms.Form):
    friend_id = forms.IntegerField(widget=forms.Select(attrs={"class": "inputtext"}))
    color = forms.ChoiceField(
        choices=(("white", "Белые (ходите первыми)"), ("black", "Чёрные")),
        initial="white",
        widget=_sel(),
    )
    time_control = forms.ChoiceField(
        choices=(
            ("0", "Без лимита"),
            ("1800", "30 минут на партию"),
            ("3600", "1 час на партию"),
            ("86400", "24 часа на партию"),
            ("259200", "3 дня на партию"),
        ),
        initial="86400",
        label="Часы",
        widget=_sel(),
        help_text="Как в настоящих шахматах: время тикает только на вашем ходу. Ноль — поражение.",
    )
    in_champ = forms.BooleanField(
        required=False, initial=True, label="Учитывать в чемпионате недели",
        widget=forms.CheckboxInput(),
    )

    def __init__(self, *args, friends=None, **kwargs):
        super().__init__(*args, **kwargs)
        friends = friends or []
        self.fields["friend_id"].widget.choices = [
            (f.id, f.name) for f in friends
        ] or [("", "Сначала добавьте друзей")]
        if not friends:
            self.fields["friend_id"].disabled = True


class MoveForm(ClassicForm, forms.Form):
    game_id = forms.IntegerField(widget=forms.HiddenInput())
    from_sq = SquareField(label="Откуда")
    to_sq = SquareField(label="Куда")


class GameActionForm(ClassicForm, forms.Form):
    """resign / draw / flag"""
    game_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(
        choices=(
            ("resign", "resign"),
            ("draw_offer", "draw_offer"),
            ("draw_accept", "draw_accept"),
            ("draw_decline", "draw_decline"),
            ("claim_flag", "claim_flag"),
        ),
        widget=forms.HiddenInput(),
    )


class PuzzleAnswerForm(ClassicForm, forms.Form):
    puzzle_id = forms.CharField(max_length=40, widget=forms.HiddenInput())
    from_sq = SquareField(label="Откуда")
    to_sq = SquareField(label="Куда")
