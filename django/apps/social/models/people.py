from __future__ import annotations
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from .fields import PgJSON

class SocialProfile(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField("accounts.User", models.DO_NOTHING, related_name="profile", db_column="user_id")
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)
    city = models.CharField(max_length=255)
    avatar_color = models.CharField(max_length=255)
    avatar_path = models.CharField(max_length=255, null=True, blank=True)
    cover_path = models.CharField(max_length=255, null=True, blank=True)
    headline = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    verified = models.BooleanField(default=False)
    gender = models.CharField(max_length=32, null=True, blank=True)
    birthday = models.DateField(null=True, blank=True)
    birthday_visibility = models.CharField(max_length=20, default="day_month")
    hometown = models.CharField(max_length=120, null=True, blank=True)
    country = models.CharField(max_length=120, null=True, blank=True)
    district = models.CharField(max_length=120, null=True, blank=True)
    relationship_status = models.CharField(max_length=40, null=True, blank=True)
    relationship_with = models.ForeignKey(
        "self", models.DO_NOTHING, null=True, blank=True, related_name="relationship_partners",
        db_column="relationship_with_id",
    )
    looking_for = PgJSON(null=True, blank=True)
    interested_in = PgJSON(null=True, blank=True)
    languages = PgJSON(null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=40, null=True, blank=True)
    show_phone = models.BooleanField(default=False)
    show_email = models.BooleanField(default=False)
    profile_visibility = models.CharField(max_length=20, default="public")
    wall_write = models.CharField(max_length=20, default="friends")
    wall_view = models.CharField(max_length=20, default="public")
    interests = models.TextField(null=True, blank=True)
    hobbies = models.TextField(null=True, blank=True)
    favorite_music = models.TextField(null=True, blank=True)
    favorite_movies = models.TextField(null=True, blank=True)
    favorite_tv = models.TextField(null=True, blank=True)
    favorite_books = models.TextField(null=True, blank=True)
    favorite_games = models.TextField(null=True, blank=True)
    favorite_quotes = models.TextField(null=True, blank=True)
    political_views = models.CharField(max_length=120, null=True, blank=True)
    religious_views = models.CharField(max_length=120, null=True, blank=True)
    life_goals = models.TextField(null=True, blank=True)
    pronouns = models.CharField(max_length=40, null=True, blank=True)
    family_status = models.CharField(max_length=40, null=True, blank=True)
    education_note = models.CharField(max_length=255, null=True, blank=True)
    workplace = models.CharField(max_length=160, null=True, blank=True)
    telegram_username = models.CharField(max_length=255, null=True, blank=True)
    invite_code = models.CharField(max_length=32, null=True, blank=True)
    invited_by = models.ForeignKey(
        "self", models.DO_NOTHING, null=True, blank=True, related_name="invitees",
        db_column="invited_by_id",
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "social_users"

    def __str__(self):
        return self.name

    def birthday_display(self) -> str | None:
        if not self.birthday:
            return None
        vis = self.birthday_visibility or "day_month"
        if vis == "hide":
            return None
        months = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
        d, m, y = self.birthday.day, months[self.birthday.month - 1], self.birthday.year
        now = timezone.now().date()
        age = now.year - y - ((now.month, now.day) < (self.birthday.month, self.birthday.day))
        if vis == "full":
            return f"{d} {m} {y} ({age})"
        if vis == "age":
            return str(age)
        return f"{d} {m}"

    @cached_property
    def avatar_url(self) -> str | None:
        from apps.social.media import media_url
        return media_url(self.avatar_path)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("profile", kwargs={"pk": self.pk})

    def languages_label(self) -> str:
        data = self.languages
        if isinstance(data, list):
            return ", ".join(map(str, data))
        return str(data or "")

    def looking_for_label(self) -> str:
        raw = self.looking_for
        if not isinstance(raw, list) or not raw:
            return ""
        labels = {
            "friendship": "Дружба", "dating": "Знакомства",
            "relationship": "Отношения", "networking": "Нетворкинг",
        }
        return ", ".join(labels.get(str(x), str(x)) for x in raw)

    def interested_in_label(self) -> str:
        raw = self.interested_in
        if not isinstance(raw, list) or not raw:
            return ""
        labels = {"men": "Мужчины", "women": "Женщины"}
        return ", ".join(labels.get(str(x), str(x)) for x in raw)

class Friendship(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="friendships_out")
    friend = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="friendships_in")
    status = models.CharField(max_length=255)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "friendships"

class Block(models.Model):
    id = models.BigAutoField(primary_key=True)
    blocker = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="blocks_out")
    blocked = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="blocks_in")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "blocks"

class Education(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="education_rows")
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, null=True, blank=True)
    field = models.CharField(max_length=255, null=True, blank=True)
    start_year = models.SmallIntegerField(null=True, blank=True)
    end_year = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "education"

class Experience(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="experiences")
    company_name = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    period = models.CharField(max_length=255)
    description = models.TextField(default="")

    class Meta:
        managed = False
        db_table = "experiences"

