"""Django forms for Poker canvas actions."""
from django import forms

from apps.social.poker import service as poker


def _sel():
    return forms.Select(attrs={"class": "inputtext"})


class ChallengeForm(forms.Form):
    friend_id = forms.IntegerField(widget=forms.Select(attrs={"class": "inputtext"}))
    stake = forms.ChoiceField(
        choices=[(s[0], s[1]) for s in poker.STAKE_LEVELS],
        initial="micro",
        label="Лимит",
        widget=_sel(),
    )

    def __init__(self, *args, friends=None, **kwargs):
        super().__init__(*args, **kwargs)
        friends = friends or []
        self.fields["friend_id"].widget.choices = [
            (f.id, f.name) for f in friends
        ] or [("", "Сначала добавьте друзей")]
        if not friends:
            self.fields["friend_id"].disabled = True


class GameActionForm(forms.Form):
    game_id = forms.IntegerField(widget=forms.HiddenInput())
    play = forms.ChoiceField(
        choices=[
            ("fold", "Фолд"),
            ("check", "Чек"),
            ("call", "Колл"),
            ("bet", "Ставка"),
            ("raise", "Рейз"),
            ("allin", "Олл-ин"),
        ],
    )
    raise_to = forms.IntegerField(required=False, min_value=0)


class LessonQuizForm(forms.Form):
    lesson = forms.CharField(max_length=40, widget=forms.HiddenInput())
    choice = forms.CharField(max_length=40)


class PuzzleAnswerForm(forms.Form):
    puzzle_id = forms.CharField(max_length=40, widget=forms.HiddenInput())
    choice = forms.CharField(max_length=40)
