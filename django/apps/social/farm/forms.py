"""Forms for Ферма canvas."""
from django import forms

from . import catalog


class PlantForm(forms.Form):
    plot_id = forms.IntegerField()
    crop = forms.ChoiceField(choices=[(c[0], c[1]) for c in catalog.CROPS])


class PlotActionForm(forms.Form):
    plot_id = forms.IntegerField()


class AnimalBuyForm(forms.Form):
    kind = forms.ChoiceField(choices=[(a[0], a[1]) for a in catalog.ANIMALS])


class AnimalActionForm(forms.Form):
    animal_id = forms.IntegerField()


class ShopForm(forms.Form):
    item = forms.ChoiceField(choices=[(s["slug"], s["title"]) for s in catalog.SHOP])
    qty = forms.IntegerField(min_value=1, max_value=20, initial=1)


class LessonQuizForm(forms.Form):
    lesson_slug = forms.CharField(max_length=40)
    choice = forms.CharField(max_length=20)


class VisitActionForm(forms.Form):
    owner_id = forms.IntegerField()
    plot_id = forms.IntegerField()
