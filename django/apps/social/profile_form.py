"""Profile edit form — sectioned classic Info; forms.ProfileForm re-exports."""
from __future__ import annotations

from django import forms
from django.db.models import Q

from apps.social.forms import ClassicForm, _birthday, _in, _ta
from apps.social.models import SocialProfile


class ProfileForm(ClassicForm, forms.ModelForm):
    GENDER = [("", "—"), ("male", "Мужской"), ("female", "Женский")]
    RELATION = [
        ("", "—"), ("single", "Не женат(а)"), ("in_a_relationship", "В отношениях"),
        ("engaged", "Помолвлен(а)"), ("married", "Женат / замужем"), ("complicated", "Всё сложно"),
    ]
    POLITICS = [
        ("", "—"), ("not_interested", "Не интересуюсь"), ("moderate", "Умеренные"),
        ("liberal", "Либеральные"), ("conservative", "Консервативные"), ("apolitical", "Вне политики"),
    ]
    LOOKING = [
        ("friendship", "Дружба"), ("dating", "Знакомства"),
        ("relationship", "Отношения"), ("networking", "Деловые контакты"),
    ]
    INTERESTED = [("men", "Мужчины"), ("women", "Женщины")]
    BIRTHDAY_VIS = [
        ("day_month", "День и месяц"), ("full", "Полная дата"),
        ("age", "Только возраст"), ("hide", "Скрыть"),
    ]
    PROFILE_VIS = [("public", "Всем"), ("friends", "Только друзьям")]
    WALL_WRITE = [("friends", "Друзья"), ("self", "Только я")]
    WALL_VIEW = [("public", "Всем"), ("friends", "Друзья"), ("self", "Только я")]
    languages_text = forms.CharField(
        required=False, label="Языки",
        widget=_in(style="width:100%"),
    )
    looking_for_choices = forms.MultipleChoiceField(
        required=False, label="Ищу", choices=LOOKING,
        widget=forms.CheckboxSelectMultiple,
    )
    interested_in_choices = forms.MultipleChoiceField(
        required=False, label="Интересуюсь", choices=INTERESTED,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = SocialProfile
        fields = (
            "name", "slug", "bio", "city", "hometown", "country", "gender", "birthday",
            "birthday_visibility", "relationship_status", "relationship_with", "political_views",
            "religious_views", "interests", "hobbies", "workplace", "education_note",
            "website", "phone", "show_phone", "show_email", "telegram_username",
            "profile_visibility", "wall_write", "wall_view",
            "favorite_music", "favorite_movies", "favorite_tv", "favorite_books",
            "favorite_quotes", "favorite_games",
        )
        labels = {
            "name": "Имя", "slug": "Короткое имя",
            "city": "Город", "hometown": "Родной город", "country": "Страна",
            "birthday": "День рождения", "birthday_visibility": "Показ дня рождения",
            "religious_views": "Религия", "website": "Сайт",
            "bio": "О себе", "interests": "Интересы", "hobbies": "Хобби",
            "education_note": "Образование", "workplace": "Место работы",
            "phone": "Телефон", "show_phone": "Показывать телефон",
            "show_email": "Показывать email",
            "telegram_username": "Имя в сети",
            "relationship_with": "С кем",
            "profile_visibility": "Кто видит профиль",
            "wall_write": "Кто пишет на стену",
            "wall_view": "Кто видит стену",
            "favorite_music": "Музыка", "favorite_movies": "Фильмы",
            "favorite_tv": "ТВ", "favorite_books": "Книги",
            "favorite_quotes": "Цитаты", "favorite_games": "Игры",
        }
        help_texts = {"slug": "vdruzya.ru/…"}
        widgets = {
            "name": _in(), "slug": _in(autocomplete="off"),
            "city": _in(), "birthday": _birthday(),
            "hometown": _in(), "country": _in(),
            "workplace": _in(style="width:100%"), "education_note": _in(style="width:100%"),
            "website": _in(style="width:100%"), "phone": _in(),
            "telegram_username": _in(style="width:100%"),
            "religious_views": _in(style="width:100%"),
            "bio": _ta(4), "interests": _ta(2), "hobbies": _ta(2),
            "favorite_music": _ta(2), "favorite_movies": _ta(2), "favorite_tv": _ta(2),
            "favorite_books": _ta(2), "favorite_quotes": _ta(2), "favorite_games": _ta(2),
        }

    SECTIONS = {
        "basic": {
            "name", "slug", "city", "hometown", "country", "gender", "birthday",
            "birthday_visibility", "relationship_status", "relationship_with",
            "political_views", "religious_views", "languages_text",
            "looking_for_choices", "interested_in_choices",
        },
        "contact": {"website", "phone", "show_phone", "show_email", "telegram_username"},
        "personal": {
            "bio", "interests", "hobbies", "favorite_music", "favorite_movies",
            "favorite_tv", "favorite_books", "favorite_quotes", "favorite_games",
        },
        "eduwork": {"workplace", "education_note"},
        "privacy": {"profile_visibility", "wall_write", "wall_view"},
        "picture": set(),
    }

    def __init__(self, *args, section="basic", **kwargs):
        super().__init__(*args, **kwargs)
        self.section = section if section in self.SECTIONS else "basic"
        self._setup_choices()
        self._setup_instance()
        keep = self.SECTIONS[self.section]
        for name in list(self.fields):
            if name not in keep:
                del self.fields[name]
        if "slug" in self.fields and self.instance and self.instance.slug:
            self.fields["slug"].help_text = f"vdruzya.ru/{self.instance.slug}"
        if "telegram_username" in self.fields:
            self.fields["telegram_username"].help_text = "как AIM / ICQ"

    def _setup_choices(self):
        self.fields["gender"] = forms.ChoiceField(
            required=False, label="Пол", choices=self.GENDER,
            widget=forms.Select(attrs={"class": "inputtext"}),
        )
        self.fields["relationship_status"] = forms.ChoiceField(
            required=False, label="Отношения", choices=self.RELATION,
            widget=forms.Select(attrs={"class": "inputtext"}),
        )
        self.fields["political_views"] = forms.ChoiceField(
            required=False, label="Политика", choices=self.POLITICS,
            widget=forms.Select(attrs={"class": "inputtext"}),
        )
        self.fields["birthday_visibility"] = forms.ChoiceField(
            required=False, label="Показ дня рождения", choices=self.BIRTHDAY_VIS,
            widget=forms.Select(attrs={"class": "inputtext"}),
        )
        for name, choices, label in (
            ("profile_visibility", self.PROFILE_VIS, "Кто видит профиль"),
            ("wall_write", self.WALL_WRITE, "Кто пишет на стену"),
            ("wall_view", self.WALL_VIEW, "Кто видит стену"),
        ):
            self.fields[name] = forms.ChoiceField(
                required=False, label=label, choices=choices,
                widget=forms.Select(attrs={"class": "inputtext"}),
            )
        if "relationship_with" in self.fields:
            self.fields["relationship_with"].required = False
            self.fields["relationship_with"].empty_label = "—"
            self.fields["relationship_with"].widget.attrs["class"] = "inputtext"

    def _setup_instance(self):
        if self.instance and self.instance.pk:
            from apps.social.services import accepted_friends
            if "relationship_with" in self.fields:
                qs = accepted_friends(self.instance)
                cur = self.instance.relationship_with_id
                if cur:
                    qs = SocialProfile.objects.filter(Q(pk__in=qs) | Q(pk=cur)).order_by("name")
                self.fields["relationship_with"].queryset = qs
            if "languages_text" in self.fields:
                self.fields["languages_text"].initial = self.instance.languages_label()
            if "looking_for_choices" in self.fields:
                raw = self.instance.looking_for
                if isinstance(raw, list):
                    self.fields["looking_for_choices"].initial = [str(x) for x in raw]
            if "interested_in_choices" in self.fields:
                raw = self.instance.interested_in
                if isinstance(raw, list):
                    self.fields["interested_in_choices"].initial = [str(x) for x in raw]
        elif "relationship_with" in self.fields:
            self.fields["relationship_with"].queryset = SocialProfile.objects.none()

    def clean_telegram_username(self):
        """Screen name (AIM / ICQ / nick) — classic Contact Info."""
        return (self.cleaned_data.get("telegram_username") or "").strip()[:255] or None

    def clean_website(self):
        from apps.social.templatetags.vd import external_url
        raw = (self.cleaned_data.get("website") or "").strip()[:255]
        return external_url(raw) or None

    def clean_slug(self):
        from apps.social.slugs import clean_short_slug
        s = clean_short_slug(self.cleaned_data["slug"])
        qs = SocialProfile.objects.filter(slug=s)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Это короткое имя уже занято.")
        return s

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "languages_text" in self.cleaned_data:
            raw = (self.cleaned_data.get("languages_text") or "").replace(";", ",")
            langs = [x.strip() for x in raw.split(",") if x.strip()]
            obj.languages = langs or None
        if "looking_for_choices" in self.cleaned_data:
            obj.looking_for = list(self.cleaned_data.get("looking_for_choices") or []) or None
        if "interested_in_choices" in self.cleaned_data:
            obj.interested_in = list(self.cleaned_data.get("interested_in_choices") or []) or None
        for f, default in (
            ("profile_visibility", "public"),
            ("wall_write", "friends"),
            ("wall_view", "public"),
        ):
            if f in self.cleaned_data:
                setattr(obj, f, self.cleaned_data.get(f) or default)
        if "relationship_status" in self.cleaned_data and (obj.relationship_status or "") not in {
            "in_a_relationship", "engaged", "married", "complicated",
        }:
            obj.relationship_with = None
        if commit:
            obj.save()
        return obj
