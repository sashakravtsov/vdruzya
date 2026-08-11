from django import forms
from django.db.models import Q
from apps.social.categories import CHOICES as GROUP_CATS
from apps.social.models import (
    Album, Comment, Community, CommunityPost, Education, Experience,
    Message, Post, SocialProfile,
)


def _in(**attrs):
    return forms.TextInput(attrs={"class": "inputtext", **attrs})


def _ta(rows=3, **attrs):
    return forms.Textarea(attrs={"rows": rows, "class": "inputtext", "style": "width:100%", **attrs})


def _file(**attrs):
    return forms.FileInput(attrs={
        "class": "inputfile",
        "accept": "image/jpeg,image/png,image/gif,image/webp",
        **attrs,
    })


class _MultiFile(forms.ClearableFileInput):
    allow_multiple_selected = True


def _files(**attrs):
    return _MultiFile(attrs={
        "class": "inputfile",
        "accept": "image/jpeg,image/png,image/gif,image/webp",
        **attrs,
    })


def _has_media(form):
    raw, files = form.data, form.files
    photos = files.getlist("photo") if files and hasattr(files, "getlist") else []
    albums = raw.getlist("album_photos") if hasattr(raw, "getlist") else []
    return bool(photos or albums)


class ProfileForm(forms.ModelForm):
    GENDER = [("", "—"), ("male", "Мужской"), ("female", "Женский")]
    RELATION = [
        ("", "—"), ("single", "Не женат"), ("in_a_relationship", "В отношениях"),
        ("engaged", "Помолвлен(а)"), ("married", "Женат"), ("complicated", "Всё сложно"),
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
    PROFILE_VIS = [("public", "Всем"), ("friends", "Только друзьям (limited)")]
    WALL_WRITE = [("friends", "Друзья"), ("self", "Только я")]
    WALL_VIEW = [("public", "Всем"), ("friends", "Друзья"), ("self", "Только я")]
    languages_text = forms.CharField(
        required=False, label="Языки",
        widget=_in(placeholder="русский, английский", style="width:100%"),
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
            "name", "slug", "headline", "bio", "city", "hometown", "country", "gender", "birthday",
            "birthday_visibility", "relationship_status", "relationship_with", "political_views",
            "religious_views", "interests", "hobbies", "workplace", "education_note",
            "website", "phone", "show_phone", "show_email", "telegram_username",
            "profile_visibility", "wall_write", "wall_view",
            "favorite_music", "favorite_movies", "favorite_tv", "favorite_books", "favorite_quotes",
        )
        labels = {
            "slug": "Короткое имя", "birthday": "День рождения",
            "birthday_visibility": "Показ дня рождения", "religious_views": "Религия",
            "education_note": "Образование", "workplace": "Место работы",
            "phone": "Телефон", "show_phone": "Показывать телефон",
            "show_email": "Показывать email",
            "telegram_username": "Имя в сети",
            "relationship_with": "С кем",
            "profile_visibility": "Кто видит профиль",
            "wall_write": "Кто пишет на стену",
            "wall_view": "Кто видит стену",
        }
        widgets = {
            "name": _in(), "slug": _in(placeholder="латиница, 5–32", autocomplete="off"),
            "headline": _in(style="width:100%"), "city": _in(),
            "birthday": forms.DateInput(attrs={"class": "inputtext", "type": "date"}),
            "hometown": _in(), "country": _in(),
            "workplace": _in(style="width:100%"), "education_note": _in(style="width:100%"),
            "website": _in(style="width:100%"), "phone": _in(),
            "telegram_username": _in(placeholder="AIM / ICQ / ник", style="width:100%"),
            "religious_views": _in(style="width:100%"),
            "bio": _ta(4), "interests": _ta(2), "hobbies": _ta(2),
            "favorite_music": _ta(2), "favorite_movies": _ta(2), "favorite_tv": _ta(2),
            "favorite_books": _ta(2), "favorite_quotes": _ta(2),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gender"] = forms.ChoiceField(
            required=False, label="Пол", choices=self.GENDER, widget=forms.Select(attrs={"class": "inputtext"}),
        )
        self.fields["relationship_status"] = forms.ChoiceField(
            required=False, label="Отношения", choices=self.RELATION, widget=forms.Select(attrs={"class": "inputtext"}),
        )
        self.fields["political_views"] = forms.ChoiceField(
            required=False, label="Политика", choices=self.POLITICS, widget=forms.Select(attrs={"class": "inputtext"}),
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
        self.fields["relationship_with"].required = False
        self.fields["relationship_with"].empty_label = "—"
        self.fields["relationship_with"].widget.attrs["class"] = "inputtext"
        if self.instance and self.instance.pk:
            from apps.social.services import accepted_friends
            qs = accepted_friends(self.instance, 200)
            cur = self.instance.relationship_with_id
            if cur:
                qs = SocialProfile.objects.filter(Q(pk__in=qs) | Q(pk=cur)).order_by("name")
            self.fields["relationship_with"].queryset = qs
            self.fields["languages_text"].initial = self.instance.languages_label()
            raw = self.instance.looking_for
            if isinstance(raw, list):
                self.fields["looking_for_choices"].initial = [str(x) for x in raw]
            raw = self.instance.interested_in
            if isinstance(raw, list):
                self.fields["interested_in_choices"].initial = [str(x) for x in raw]
        else:
            self.fields["relationship_with"].queryset = SocialProfile.objects.none()

    def clean_telegram_username(self):
        raw = (self.cleaned_data.get("telegram_username") or "").strip().lstrip("@")
        return raw[:255] or None

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
        raw = (self.cleaned_data.get("languages_text") or "").replace(";", ",")
        langs = [x.strip() for x in raw.split(",") if x.strip()]
        obj.languages = langs or None
        obj.looking_for = list(self.cleaned_data.get("looking_for_choices") or []) or None
        obj.interested_in = list(self.cleaned_data.get("interested_in_choices") or []) or None
        for f, default in (
            ("profile_visibility", "public"),
            ("wall_write", "friends"),
            ("wall_view", "public"),
        ):
            setattr(obj, f, self.cleaned_data.get(f) or default)
        if (obj.relationship_status or "") not in {
            "in_a_relationship", "engaged", "married", "complicated",
        }:
            obj.relationship_with = None
        if commit:
            obj.save()
        return obj


class PostForm(forms.ModelForm):
    """Classic FB wall: text + photo."""
    photo = forms.ImageField(required=False, label="Фото", widget=_files())

    class Meta:
        model = Post
        fields = ("body", "visibility")
        widgets = {
            "body": _ta(3, placeholder="Написать на стену…"),
            "visibility": forms.Select(choices=[("public", "Всем"), ("friends", "Друзьям"), ("private", "Только мне")]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not _has_media(self):
            self.add_error("body", "Напишите текст или выберите фото.")
        return data


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": _in(style="width:80%", placeholder="Комментарий")}


class MessageForm(forms.ModelForm):
    photo = forms.ImageField(required=False, label="Фото", widget=_file())

    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": _ta(2, placeholder="Написать сообщение…", style="width:80%")}

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not self.files.get("photo"):
            self.add_error("body", "Напишите текст или приложите фото.")
        return data


class ComposeMessageForm(forms.Form):
    to = forms.MultipleChoiceField(
        choices=(),
        widget=forms.SelectMultiple(attrs={"class": "inputtext", "size": "6", "style": "width:100%;max-width:420px"}),
    )
    subject = forms.CharField(
        required=False, max_length=160, label="Тема",
        widget=_in(placeholder="Тема (необязательно)", style="width:100%"),
    )
    body = forms.CharField(
        required=False,
        widget=_ta(4, placeholder="Сообщение…", style="width:100%"),
    )
    photo = forms.ImageField(required=False, label="Фото", widget=_file())

    def __init__(self, friends, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to"].choices = [(str(p.id), p.name) for p in friends]

    def clean(self):
        data = super().clean()
        if not data.get("to"):
            self.add_error("to", "Выберите хотя бы одного друга.")
        if not (data.get("body") or "").strip() and not self.files.get("photo"):
            self.add_error("body", "Напишите текст или приложите фото.")
        return data


class AlbumForm(forms.ModelForm):
    cover = forms.ImageField(required=False, label="Обложка", widget=_file())

    class Meta:
        model = Album
        fields = ("title", "description", "visibility")
        widgets = {
            "title": _in(style="width:100%", placeholder="Название альбома"),
            "description": _ta(2, placeholder="Описание (необязательно)"),
            "visibility": forms.Select(choices=[("friends", "Друзьям"), ("public", "Всем"), ("private", "Только мне")]),
        }


class PhotoUploadForm(forms.Form):
    photo = forms.ImageField(label="Файл", widget=_file())
    title = forms.CharField(
        max_length=120, label="Название",
        widget=_in(style="width:100%", placeholder="Короткое название для подписи"),
    )


class CreateGroupForm(forms.Form):
    name = forms.CharField(max_length=255, widget=_in(style="width:100%", placeholder="Название группы"))
    category = forms.ChoiceField(choices=GROUP_CATS, widget=forms.Select())
    privacy = forms.ChoiceField(
        choices=[("public", "Открытая"), ("closed", "Закрытая")],
        initial="public",
        widget=forms.Select(),
    )
    short_description = forms.CharField(
        required=False, max_length=200,
        widget=_ta(2, placeholder="Коротко о группе (необязательно)"),
    )


class GroupForm(forms.ModelForm):
    picture = forms.ImageField(required=False, label="Картинка", widget=_file())

    class Meta:
        model = Community
        fields = (
            "name", "slug", "category", "short_description", "description",
            "privacy", "join_mode", "posting_policy", "messaging_enabled",
        )
        labels = {
            "slug": "Короткое имя",
            "short_description": "Последние новости",
            "posting_policy": "Кто пишет",
            "messaging_enabled": "Сообщения группы",
        }
        widgets = {
            "name": _in(style="width:100%"),
            "slug": _in(placeholder="латиница, 5–32", autocomplete="off"),
            "short_description": _ta(2, maxlength="200"),
            "description": _ta(4),
            "privacy": forms.Select(choices=[("public", "Открытая"), ("closed", "Закрытая")]),
            "join_mode": forms.Select(choices=[("open", "Свободный вход"), ("request", "По заявке")]),
            "posting_policy": forms.Select(choices=[
                ("members", "Только участники"), ("admins", "Только админы"), ("everyone", "Все (открытая стена)"),
            ]),
            "messaging_enabled": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"] = forms.ChoiceField(choices=GROUP_CATS, widget=forms.Select())

    def clean_slug(self):
        from apps.social.slugs import clean_short_slug
        s = clean_short_slug(self.cleaned_data["slug"])
        qs = Community.objects.filter(slug=s)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Это короткое имя уже занято.")
        return s


class CommunityPostForm(forms.ModelForm):
    photo = forms.ImageField(required=False, label="Фото", widget=_files())
    board = forms.ChoiceField(
        choices=[("discussion", "Доска обсуждений"), ("wall", "Стена группы")],
        initial="discussion",
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = CommunityPost
        fields = ("body",)
        widgets = {"body": _ta(3, placeholder="Написать…")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not _has_media(self):
            self.add_error("body", "Напишите текст или выберите фото.")
        return data


class StatusForm(forms.Form):
    headline = forms.CharField(max_length=255, required=False, widget=_in(style="width:100%", placeholder="Что у вас нового?"))


class GroupEventForm(forms.Form):
    title = forms.CharField(max_length=160, widget=_in(placeholder="Название события"))
    place = forms.CharField(max_length=160, widget=_in(placeholder="Место"))
    starts_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "inputtext"}))


class PasswordForm(forms.Form):
    old = forms.CharField(label="Текущий пароль", widget=forms.PasswordInput(attrs={"class": "inputtext"}))
    new1 = forms.CharField(label="Новый пароль", min_length=8, widget=forms.PasswordInput(attrs={"class": "inputtext"}))
    new2 = forms.CharField(label="Ещё раз", min_length=8, widget=forms.PasswordInput(attrs={"class": "inputtext"}))

    def clean(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        data = super().clean()
        if data.get("new1") != data.get("new2"):
            self.add_error("new2", "Пароли не совпадают.")
        elif data.get("new1"):
            try:
                validate_password(data["new1"])
            except ValidationError as exc:
                self.add_error("new1", exc)
        return data


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ("institution", "degree", "field", "start_year", "end_year")
        labels = {"institution": "Учебное заведение", "degree": "Степень", "field": "Специальность", "start_year": "С", "end_year": "По"}
        widgets = {f: _in() for f in ("institution", "degree", "field", "start_year", "end_year")}


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = ("company_name", "position", "period", "description")
        labels = {"company_name": "Компания", "position": "Должность", "period": "Период", "description": "Описание"}
        widgets = {
            "company_name": _in(), "position": _in(), "period": _in(), "description": _ta(2),
        }
