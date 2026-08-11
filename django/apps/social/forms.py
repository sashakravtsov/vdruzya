from django import forms
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
    """Classic FB-era file picker — no drag-and-drop chrome."""
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


class ProfileForm(forms.ModelForm):
    GENDER = [("", "—"), ("male", "Мужской"), ("female", "Женский"), ("other", "Другой")]
    RELATION = [
        ("", "—"), ("single", "Не женат"), ("in_a_relationship", "В отношениях"),
        ("engaged", "Помолвлен(а)"), ("married", "Женат"), ("complicated", "Всё сложно"),
        ("open", "Свободные отношения"),
    ]
    POLITICS = [
        ("", "—"), ("not_interested", "Не интересуюсь"), ("moderate", "Умеренные"),
        ("liberal", "Либеральные"), ("conservative", "Консервативные"), ("apolitical", "Вне политики"),
    ]
    languages_text = forms.CharField(
        required=False, label="Языки",
        widget=_in(placeholder="русский, английский", style="width:100%"),
    )

    class Meta:
        model = SocialProfile
        fields = (
            "name", "slug", "headline", "bio", "city", "hometown", "country", "gender", "birthday",
            "relationship_status", "political_views", "interests", "hobbies", "workplace", "website",
            "favorite_music", "favorite_movies", "favorite_tv", "favorite_books", "favorite_quotes",
        )
        labels = {"slug": "Короткое имя", "birthday": "День рождения"}
        widgets = {
            "name": _in(), "slug": _in(placeholder="латиница, 5–32", autocomplete="off"),
            "headline": _in(style="width:100%"), "city": _in(),
            "birthday": forms.DateInput(attrs={"class": "inputtext", "type": "date"}),
            "hometown": _in(), "country": _in(),
            "gender": forms.Select(attrs={"class": "inputtext"}, choices=[]),
            "relationship_status": forms.Select(attrs={"class": "inputtext"}, choices=[]),
            "political_views": forms.Select(attrs={"class": "inputtext"}, choices=[]),
            "workplace": _in(style="width:100%"), "website": _in(style="width:100%"),
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
        if self.instance and self.instance.pk:
            self.fields["languages_text"].initial = self.instance.languages_label()

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
        if commit:
            obj.save()
        return obj


class PostForm(forms.ModelForm):
    photo = forms.ImageField(required=False, label="Фото", widget=_files())
    poll_options = forms.CharField(
        required=False, label="Опрос",
        widget=_ta(2, placeholder="Варианты с новой строки (от 2) — необязательно"),
    )
    topic = forms.ChoiceField(required=False, label="Тема")
    mood = forms.ChoiceField(required=False, label="Настроение")
    emoji = forms.CharField(required=False, max_length=16, label="Эмодзи", widget=_in(style="width:60px"))
    sticker = forms.ChoiceField(required=False, label="Стикер")

    class Meta:
        model = Post
        fields = ("body", "visibility", "topic", "mood", "emoji", "sticker")
        widgets = {
            "body": _ta(3, placeholder="Написать на стену…"),
            "visibility": forms.Select(choices=[("public", "Всем"), ("friends", "Друзьям"), ("private", "Только мне")]),
        }

    def __init__(self, *args, **kwargs):
        from apps.social.models import Sticker
        from apps.social.wall_meta import MOODS, TOPICS
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False
        self.fields["topic"].choices = TOPICS
        self.fields["mood"].choices = MOODS
        sticks = [("", "—")] + list(
            Sticker.objects.filter(is_active=True).order_by("sort_order").values_list("slug", "title")[:24]
        )
        self.fields["sticker"].choices = sticks

    def clean(self):
        data = super().clean()
        raw = self.data
        files = self.files.getlist("photo") if self.files and hasattr(self.files, "getlist") else []
        albums = raw.getlist("album_photos") if hasattr(raw, "getlist") else []
        if not (data.get("body") or "").strip() and not data.get("photo") and not files and not albums and not (
            data.get("poll_options") or ""
        ).strip() and not data.get("sticker"):
            self.add_error("body", "Напишите текст или выберите фото.")
        return data


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {"body": _in(style="width:80%", placeholder="Комментарий")}


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": _in(style="width:80%")}


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
    cover = forms.ImageField(required=False, label="Обложка", widget=_file())

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
            "messaging_enabled": "Чат группы",
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
    poll_options = forms.CharField(
        required=False, label="Опрос",
        widget=_ta(2, placeholder="Варианты с новой строки (от 2) — необязательно"),
    )
    board = forms.ChoiceField(
        choices=[("discussion", "Доска обсуждений"), ("wall", "Стена группы")],
        initial="discussion",
        widget=forms.HiddenInput(),
    )
    mood = forms.ChoiceField(required=False, label="Настроение")
    emoji = forms.CharField(required=False, max_length=16, label="Эмодзи", widget=_in(style="width:60px"))

    class Meta:
        model = CommunityPost
        fields = ("body", "mood", "emoji")
        widgets = {"body": _ta(3, placeholder="Написать…", required=False)}

    def __init__(self, *args, **kwargs):
        from apps.social.wall_meta import MOODS
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False
        self.fields["mood"].choices = MOODS

    def clean(self):
        data = super().clean()
        raw = self.data
        files = self.files.getlist("photo") if self.files and hasattr(self.files, "getlist") else []
        if hasattr(raw, "getlist"):
            albums = raw.getlist("album_photos")
        else:
            albums = raw.get("album_photos") or []
            albums = albums if isinstance(albums, (list, tuple)) else [albums]
        if not (data.get("body") or "").strip() and not data.get("photo") and not files and not albums and not (
            data.get("poll_options") or ""
        ).strip():
            self.add_error("body", "Напишите текст или выберите фото.")
        return data


class GroupEventForm(forms.Form):
    title = forms.CharField(max_length=160, widget=_in(placeholder="Название события"))
    place = forms.CharField(max_length=160, widget=_in(placeholder="Место"))
    starts_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "inputtext"}))


class GroupInviteForm(forms.Form):
    friend_id = forms.IntegerField(widget=forms.HiddenInput)


class StatusForm(forms.Form):
    headline = forms.CharField(max_length=255, required=False, widget=_in(style="width:100%", placeholder="Что у вас нового?"))


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
