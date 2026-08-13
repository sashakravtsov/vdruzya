"""Unmanaged dating tables (created by deploy/ensure-dating-modules.py)."""
from django.db import models

from apps.social.models import SocialProfile


class DatingProfile(models.Model):
    social_user = models.OneToOneField(
        SocialProfile,
        on_delete=models.DO_NOTHING,
        primary_key=True,
        db_column="social_user_id",
        related_name="+",
    )
    headline = models.CharField(max_length=120, blank=True, default="")
    about = models.TextField(blank=True, default="")
    intent = models.CharField(max_length=24, default="dating")  # dating|friendship|chat|serious
    prompts_json = models.TextField(blank=True, default="[]")
    age_min = models.IntegerField(default=18)
    age_max = models.IntegerField(default=99)
    gender_pref = models.CharField(max_length=12, default="any")  # any|male|female
    discoverable = models.BooleanField(default=True)
    superlikes_left = models.IntegerField(default=3)
    superlikes_on = models.DateField(null=True, blank=True)
    views_today = models.IntegerField(default=0)
    likes_today = models.IntegerField(default=0)
    daily_on = models.DateField(null=True, blank=True)
    streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    last_active_on = models.DateField(null=True, blank=True)
    matches_n = models.IntegerField(default=0)
    likes_sent = models.IntegerField(default=0)
    likes_got = models.IntegerField(default=0)
    spark_points = models.IntegerField(default=0)
    achievements = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dating_profiles"


class DatingSwipe(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="from_id", related_name="+",
    )
    to_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="to_id", related_name="+",
    )
    action = models.CharField(max_length=12)  # like|pass|super
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dating_swipes"


class DatingMatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_a = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="user_a_id", related_name="+",
    )
    user_b = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="user_b_id", related_name="+",
    )
    opener = models.CharField(max_length=200, blank=True, default="")
    seen_a = models.BooleanField(default=False)
    seen_b = models.BooleanField(default=False)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dating_matches"


class DatingVisit(models.Model):
    id = models.BigAutoField(primary_key=True)
    viewer = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="viewer_id", related_name="+",
    )
    viewed = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="viewed_id", related_name="+",
    )
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dating_visits"
