from django import forms
from django.db.models import Q
from django.forms.widgets import SelectDateWidget
from django.utils import timezone
from apps.social.categories import CHOICES as GROUP_CATS
from apps.social.models import (
    Album, Community, CommunityPost, Education, Experience,
    Message, Post, SocialProfile,
)


def _in(**attrs):
    return forms.TextInput(attrs={"class": "inputtext", **attrs})


def _ta(rows=3, **attrs):
    return forms.Textarea(attrs={"rows": rows, "class": "inputtext", "style": "width:100%", **attrs})


def _file(**attrs):
    return forms.FileInput(attrs={
        "class": "inputfile",
        "accept": "image/jpeg,image/png,image/gif",
        **attrs,
    })


def _media_file(**attrs):
    """Single file: classic photos or one video — Inbox / compose."""
    return forms.FileInput(attrs={
        "class": "inputfile",
        "accept": (
            "image/jpeg,image/png,image/gif,"
            "video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
        ),
        **attrs,
    })


def _birthday():
    """FB 2005 birthday — three selects, never HTML5 date."""
    y = timezone.localdate().year
    return SelectDateWidget(
        years=range(y, 1929, -1),
        months={
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
        },
        empty_label=("год", "мес", "день"),
        attrs={"class": "inputtext"},
    )


class _MultiFile(forms.ClearableFileInput):
    allow_multiple_selected = True


def _files(**attrs):
    return _MultiFile(attrs={
        "class": "inputfile",
        "accept": (
            "image/jpeg,image/png,image/gif,"
            "video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
        ),
        **attrs,
    })


class MultiFileField(forms.FileField):
    """FileField that accepts the list returned by <input multiple> widgets."""

    def clean(self, data, initial=None):
        if data is False:
            return False
        if data in self.empty_values:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        out = []
        single = forms.FileField(
            required=True,
            allow_empty_file=self.allow_empty_file,
            max_length=self.max_length,
        )
        for item in data:
            cleaned = single.clean(item, initial)
            if cleaned:
                out.append(cleaned)
        return out


class ClassicForm:
    """FB 2006 chrome — no HTML5 required / minlength on widgets."""
    use_required_attribute = False


def _has_media(form):
    files = form.files
    photos = files.getlist("photo") if files and hasattr(files, "getlist") else []
    return bool(photos)


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
        help_texts = {
            "slug": "vdruzya.ru/…",
        }
        widgets = {
            "name": _in(), "slug": _in(autocomplete="off"),
            "city": _in(),
            "birthday": _birthday(),
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
        if "relationship_with" in self.fields:
            self.fields["relationship_with"].required = False
            self.fields["relationship_with"].empty_label = "—"
            self.fields["relationship_with"].widget.attrs["class"] = "inputtext"
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
        keep = self.SECTIONS[self.section]
        for name in list(self.fields):
            if name not in keep:
                del self.fields[name]
        if "slug" in self.fields and self.instance and self.instance.slug:
            self.fields["slug"].help_text = f"vdruzya.ru/{self.instance.slug}"
        if "telegram_username" in self.fields:
            self.fields["telegram_username"].help_text = "как AIM / ICQ"

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


class PostForm(ClassicForm, forms.ModelForm):
    """Classic FB wall: text + photo/video. simple=True → profile wall (no visibility UI)."""
    # MultiFileField: <input multiple> returns a list; ImageField rejects video MIME.
    photo = MultiFileField(required=False, label="Фото / видео", widget=_files())

    class Meta:
        model = Post
        fields = ("body", "visibility")
        widgets = {
            "body": _ta(3),
            "visibility": forms.Select(choices=[("public", "Всем"), ("friends", "Друзьям"), ("private", "Только мне")]),
        }

    def __init__(self, *args, simple=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.simple = simple
        self.fields["body"].required = False
        if simple:
            # Keep multi-file widget; classic wall accepts several photos or one video.
            self.fields.pop("visibility", None)

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not _has_media(self):
            self.add_error("body", "Напишите текст или выберите фото / видео.")
        return data


class NoteForm(ClassicForm, forms.Form):
    """FB Notes (mid-2006) — title + body (+ optional photo on same media disk)."""
    title = forms.CharField(max_length=120, label="Заголовок", widget=_in(style="width:100%"))
    body = forms.CharField(label="Текст", widget=_ta(8, style="width:100%"))
    visibility = forms.ChoiceField(
        choices=[("public", "Всем"), ("friends", "Друзьям"), ("private", "Только мне")],
        initial="public",
        widget=forms.Select(),
    )
    photo = forms.ImageField(required=False, label="Фото", widget=_file())

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:120]

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите текст заметки.")
        return body


class CommentForm(ClassicForm, forms.Form):
    """Flat comment body for wall / group / photo (classic FB — one form)."""
    body = forms.CharField(
        max_length=2000,
        widget=_in(style="width:80%", maxlength="2000", autocomplete="off"),
    )

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите комментарий.")
        return body


class GroupDocForm(ClassicForm, forms.Form):
    title = forms.CharField(max_length=200, widget=_in(style="width:100%"))
    body = forms.CharField(required=False, widget=_ta(10, style="width:100%"))

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Укажите название документа.")
        return title[:200]

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()


class MessageForm(ClassicForm, forms.ModelForm):
    photo = forms.FileField(required=False, label="Фото / видео", widget=_media_file())
    reply_to = forms.IntegerField(required=False, widget=forms.HiddenInput())
    sticker = forms.ChoiceField(required=False, choices=(), widget=forms.Select(attrs={"class": "inputtext"}))

    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": _ta(2, style="width:80%")}

    def __init__(self, *args, stickers=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "— без стикера —")]
        for s in stickers or []:
            choices.append((str(s.id), s.title))
        self.fields["sticker"].choices = choices

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not self.files.get("photo") and not data.get("sticker"):
            self.add_error("body", "Напишите текст, приложите фото / видео или выберите стикер.")
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
        widget=_ta(4, style="width:100%"),
    )
    photo = forms.FileField(required=False, label="Фото / видео", widget=_media_file())

    def __init__(self, friends, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to"].choices = [("", "— выберите друга —")] + [(str(p.id), p.name) for p in friends]

    def clean(self):
        data = super().clean()
        if not data.get("to"):
            self.add_error("to", "Выберите друга.")
        if not (data.get("body") or "").strip() and not self.files.get("photo"):
            self.add_error("body", "Напишите текст или приложите фото / видео.")
        return data


class AlbumForm(ClassicForm, forms.ModelForm):
    cover = forms.ImageField(required=False, label="Обложка", widget=_file())

    class Meta:
        model = Album
        fields = ("title", "description", "visibility")
        widgets = {
            "title": _in(style="width:100%"),
            "description": _ta(2),
            "visibility": forms.Select(choices=[("friends", "Друзьям"), ("public", "Всем"), ("private", "Только мне")]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


class PhotoUploadForm(ClassicForm, forms.Form):
    """Album upload — multi-select; files read via request.FILES.getlist('photo')."""
    photo = MultiFileField(label="Файлы", required=False, widget=_files(
        accept="image/jpeg,image/png,image/gif",
    ))
    title = forms.CharField(
        max_length=120, required=False, label="Название",
        widget=_in(style="width:100%"),
    )


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
        inst = getattr(self, "instance", None)
        if inst and inst.pk and (inst.topic or "") != "wall" and not self.is_bound:
            self.fields["subject"].initial = inst.subject
            self.fields["body"].initial = inst.body_text

    def clean(self):
        data = super().clean()
        board = data.get("board") or "discussion"
        body = (data.get("body") or "").strip()
        subject = (data.get("subject") or "").strip()
        has_media = _has_media(self)
        if board == "discussion":
            if not subject:
                self.add_error("subject", "Укажите тему.")
            if not body and not has_media:
                self.add_error("body", "Напишите сообщение.")
        elif not body and not has_media:
            self.add_error("body", "Напишите текст или выберите фото / видео.")
        return data


class StatusForm(ClassicForm, forms.Form):
    headline = forms.CharField(
        max_length=255, required=False,
        widget=_in(style="width:170px", autocomplete="off"),
    )
    place = forms.ChoiceField(
        required=False,
        choices=[("", "— без места —")],
        widget=forms.Select(attrs={"class": "inputtext"}),
    )

    def __init__(self, *args, places=None, **kwargs):
        super().__init__(*args, **kwargs)
        opts = [("", "— без места —")]
        for p in places or []:
            label = p.name
            if p.city:
                label = f"{p.name} ({p.city})"
            opts.append((str(p.id), label))
        self.fields["place"].choices = opts

    def clean_place(self):
        raw = self.cleaned_data.get("place") or ""
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None


class EventForm(ClassicForm, forms.Form):
    """Classic Events create — text date, no datetime-local."""
    title = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    place = forms.CharField(max_length=160, required=False, widget=_in(style="width:100%"))
    starts_at = forms.CharField(
        max_length=32,
        widget=_in(style="width:160px"),
        help_text="ДД.ММ.ГГГГ ЧЧ:ММ",
    )
    description = forms.CharField(required=False, widget=_ta(3, style="width:100%"))

    def clean_starts_at(self):
        from apps.social.events import parse_starts
        starts = parse_starts(self.cleaned_data.get("starts_at"))
        if not starts:
            raise forms.ValidationError("Укажите дату, например 15.09.2006 19:00")
        return starts

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]

    def clean_place(self):
        return (self.cleaned_data.get("place") or "").strip()[:160]


class GiftSendForm(ClassicForm, forms.Form):
    """Send a classic Gift (sticker) to a friend."""
    to = forms.ModelChoiceField(
        queryset=SocialProfile.objects.none(),
        empty_label="— выберите друга —",
        widget=forms.Select(attrs={"class": "inputtext"}),
    )
    gift = forms.CharField(max_length=80, widget=forms.HiddenInput())
    message = forms.CharField(
        max_length=500, required=False,
        widget=_ta(2, style="width:100%"),
    )

    def clean_gift(self):
        slug = (self.cleaned_data.get("gift") or "").strip()
        if not slug:
            raise forms.ValidationError("Выберите подарок")
        return slug



class PasswordForm(ClassicForm, forms.Form):
    old = forms.CharField(label="Текущий пароль", widget=forms.PasswordInput(attrs={"class": "inputtext"}))
    new1 = forms.CharField(label="Новый пароль", widget=forms.PasswordInput(attrs={"class": "inputtext"}))
    new2 = forms.CharField(label="Ещё раз", widget=forms.PasswordInput(attrs={"class": "inputtext"}))

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


class EducationForm(ClassicForm, forms.ModelForm):
    class Meta:
        model = Education
        fields = ("institution", "degree", "field", "start_year", "end_year")
        labels = {"institution": "Учебное заведение", "degree": "Степень", "field": "Специальность", "start_year": "С", "end_year": "По"}
        widgets = {f: _in() for f in ("institution", "degree", "field", "start_year", "end_year")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("degree", "field", "start_year", "end_year"):
            self.fields[name].required = False


class ExperienceForm(ClassicForm, forms.ModelForm):
    class Meta:
        model = Experience
        fields = ("company_name", "position", "period", "description")
        labels = {"company_name": "Компания", "position": "Должность", "period": "Период", "description": "Описание"}
        widgets = {
            "company_name": _in(), "position": _in(), "period": _in(), "description": _ta(2),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("period", "description", "position"):
            self.fields[name].required = False


class PageForm(ClassicForm, forms.Form):
    """Create / edit a public Page (Страница)."""
    name = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    industry = forms.ChoiceField(choices=[], widget=forms.Select())
    city = forms.CharField(max_length=120, required=False, widget=_in(style="width:100%"))
    description = forms.CharField(required=False, widget=_ta(4, style="width:100%"))

    def __init__(self, *args, **kwargs):
        from apps.social.page_categories import CHOICES
        super().__init__(*args, **kwargs)
        self.fields["industry"].choices = CHOICES

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:160]

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()[:120]

    def clean_description(self):
        return (self.cleaned_data.get("description") or "").strip()


class PagePostForm(ClassicForm, forms.Form):
    """Admin update on a Page wall."""
    body = forms.CharField(required=False, widget=_ta(3, style="width:100%"))
    photo = MultiFileField(required=False, label="Фото / видео", widget=_files())

    def clean(self):
        data = super().clean()
        if not (data.get("body") or "").strip() and not self.files.get("photo"):
            self.add_error("body", "Напишите текст или выберите фото / видео.")
        return data


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

    def __init__(self, *args, allow_upload=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_upload = allow_upload
        if not allow_upload:
            self.fields.pop("video", None)

    def clean_url(self):
        from apps.social.classic_extra import normalize_url
        return normalize_url(self.cleaned_data.get("url") or "")

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]

    def clean(self):
        data = super().clean()
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
    place = forms.CharField(max_length=120, required=False, widget=_in(style="width:100%"))
    description = forms.CharField(required=False, widget=_ta(4, style="width:100%"))
    photo = forms.ImageField(required=False, label="Фото", widget=_file())

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()[:160]


class FriendListForm(ClassicForm, forms.Form):
    name = forms.CharField(max_length=120, widget=_in(style="width:100%"))

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:120]


class PlaceForm(ClassicForm, forms.Form):
    name = forms.CharField(max_length=160, widget=_in(style="width:100%"))
    city = forms.CharField(max_length=120, required=False, widget=_in(style="width:100%"))
    address = forms.CharField(max_length=255, required=False, widget=_in(style="width:100%"))

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()[:160]


class CheckinForm(ClassicForm, forms.Form):
    message = forms.CharField(max_length=500, required=False, widget=_ta(2, style="width:100%"))


class QuestionForm(ClassicForm, forms.Form):
    body = forms.CharField(max_length=500, widget=_ta(3, style="width:100%"))

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите вопрос.")
        return body[:500]


class QuestionAnswerForm(ClassicForm, forms.Form):
    body = forms.CharField(max_length=500, widget=_ta(2, style="width:100%"))

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Напишите ответ.")
        return body[:500]


class PlaceReviewForm(ClassicForm, forms.Form):
    stars = forms.TypedChoiceField(
        coerce=int,
        choices=[(i, f"{i}") for i in range(1, 6)],
        initial=5,
        widget=forms.Select(attrs={"class": "inputtext"}),
    )
    body = forms.CharField(max_length=500, required=False, widget=_ta(2, style="width:100%"))

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()[:500]


class PollForm(ClassicForm, forms.Form):
    question = forms.CharField(max_length=500, widget=_ta(2, style="width:100%"))
    options = forms.CharField(
        widget=_ta(4, style="width:100%"),
        help_text="По одному варианту на строку (минимум 2).",
    )

    def clean_question(self):
        q = (self.cleaned_data.get("question") or "").strip()
        if not q:
            raise forms.ValidationError("Напишите вопрос опроса.")
        return q[:500]

    def clean_options(self):
        raw = self.cleaned_data.get("options") or ""
        opts = []
        for line in raw.splitlines():
            body = line.strip()[:255]
            if body and body not in opts:
                opts.append(body)
        if len(opts) < 2:
            raise forms.ValidationError("Нужно минимум два варианта ответа.")
        return opts[:8]

