"""Forms for Знакомства canvas."""
from django import forms

from .tips import PROMPTS


class ProfileForm(forms.Form):
    headline = forms.CharField(max_length=120, required=False, label="Заголовок", widget=forms.TextInput(attrs={"class":"inputtext","size":"40"}))
    about = forms.CharField(required=False, label="О себе", widget=forms.Textarea(attrs={"rows": 4, "cols": 48, "class":"inputtext"}))
    intent = forms.ChoiceField(
        choices=(
            ("dating", "Знакомства"),
            ("friendship", "Дружба"),
            ("chat", "Общение"),
            ("serious", "Серьёзные отношения"),
        ),
        label="Я здесь для",
    )
    age_min = forms.IntegerField(min_value=18, max_value=99, label="Возраст от")
    age_max = forms.IntegerField(min_value=18, max_value=99, label="Возраст до")
    gender_pref = forms.ChoiceField(
        choices=(("any", "Все"), ("female", "Девушки"), ("male", "Парни")),
        label="Показывать",
    )
    discoverable = forms.BooleanField(required=False, label="Показывать меня в ленте")
    prompt1_key = forms.ChoiceField(choices=[(k, v) for k, v in PROMPTS], required=False)
    prompt1_answer = forms.CharField(max_length=160, required=False, widget=forms.TextInput(attrs={"class":"inputtext","size":"40"}))
    prompt2_key = forms.ChoiceField(choices=[(k, v) for k, v in PROMPTS], required=False)
    prompt2_answer = forms.CharField(max_length=160, required=False, widget=forms.TextInput(attrs={"class":"inputtext","size":"40"}))
    prompt3_key = forms.ChoiceField(choices=[(k, v) for k, v in PROMPTS], required=False)
    prompt3_answer = forms.CharField(max_length=160, required=False, widget=forms.TextInput(attrs={"class":"inputtext","size":"40"}))


class SwipeForm(forms.Form):
    target_id = forms.IntegerField()
    swipe_action = forms.ChoiceField(choices=(("like", "like"), ("pass", "pass"), ("super", "super")))


class TipQuizForm(forms.Form):
    tip_slug = forms.CharField(max_length=40)
    choice = forms.CharField(max_length=20)
