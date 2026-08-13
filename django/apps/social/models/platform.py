"""First-party Platform app state (installs / Causes) — unmanaged, ensured on deploy."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class AppInstall(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="app_installs")
    app_slug = models.CharField(max_length=40)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_installs"
        unique_together = (("social_user", "app_slug"),)


class AppCauseJoin(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="cause_joins")
    cause_slug = models.CharField(max_length=40)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_cause_joins"
        unique_together = (("social_user", "cause_slug"),)


class AppTruthAsk(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="truth_asks_out",
        db_column="from_user_id",
    )
    to_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="truth_asks_in",
        db_column="to_user_id",
    )
    question = models.CharField(max_length=300)
    answer = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_truth_asks"
