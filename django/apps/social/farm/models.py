"""Unmanaged farm tables (deploy/ensure-farm-modules.py)."""
from django.db import models

from apps.social.models import SocialProfile


class FarmProfile(models.Model):
    social_user = models.OneToOneField(
        SocialProfile, on_delete=models.DO_NOTHING, primary_key=True,
        db_column="social_user_id", related_name="+",
    )
    chips = models.BigIntegerField(default=1_000_000)
    xp = models.IntegerField(default=0)
    plots_unlocked = models.IntegerField(default=6)
    harvests = models.IntegerField(default=0)
    plants = models.IntegerField(default=0)
    helps = models.IntegerField(default=0)
    steals = models.IntegerField(default=0)
    water_cans = models.IntegerField(default=5)
    fertilizer = models.IntegerField(default=1)
    boosts = models.IntegerField(default=0)
    play_streak = models.IntegerField(default=0)
    best_streak = models.IntegerField(default=0)
    last_play_on = models.DateField(null=True, blank=True)
    daily_bonus_on = models.DateField(null=True, blank=True)
    bankrupt_until = models.DateTimeField(null=True, blank=True)
    reset_count = models.IntegerField(default=0)
    achievements = models.TextField(blank=True, default="")
    lesson_slugs = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "farm_profiles"


class FarmPlot(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="owner_id", related_name="+",
    )
    idx = models.IntegerField(default=0)
    crop_slug = models.CharField(max_length=24, blank=True, default="")
    state = models.CharField(max_length=12, default="empty")  # empty|growing|ready|withered
    planted_at = models.DateTimeField(null=True, blank=True)
    watered = models.BooleanField(default=False)
    fertilized = models.BooleanField(default=False)
    ready_at = models.DateTimeField(null=True, blank=True)
    wither_at = models.DateTimeField(null=True, blank=True)
    stolen = models.BooleanField(default=False)
    helper_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "farm_plots"


class FarmAnimal(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="owner_id", related_name="+",
    )
    kind = models.CharField(max_length=24)
    fed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "farm_animals"


class FarmVisitLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="actor_id", related_name="+",
    )
    owner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="owner_id", related_name="+",
    )
    plot = models.ForeignKey(
        FarmPlot, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="plot_id", related_name="+",
    )
    kind = models.CharField(max_length=12)  # help|steal
    amount = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "farm_visit_logs"
