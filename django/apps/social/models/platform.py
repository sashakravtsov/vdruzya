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


class DevApp(models.Model):
    """User-registered App Center entry (first-party canvas + OAuth-lite link-out).

    Soft ban: no third-party hosted canvas/iframe — launch is redirect + REST API.
    """
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="dev_apps",
        db_column="owner_id",
    )
    slug = models.CharField(max_length=40)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=20, default="utilities")
    blurb = models.CharField(max_length=200, blank=True, default="")
    detail = models.CharField(max_length=500, blank=True, default="")
    website_url = models.CharField(max_length=255, blank=True, default="")
    callback_url = models.CharField(max_length=255, blank=True, default="")
    api_key = models.CharField(max_length=48, blank=True, default="")
    api_secret = models.CharField(max_length=64, blank=True, default="")
    published = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "dev_apps"


class AppOAuthCode(models.Model):
    id = models.BigAutoField(primary_key=True)
    app_slug = models.CharField(max_length=40)
    social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="app_oauth_codes",
    )
    code = models.CharField(max_length=64)
    redirect_uri = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_oauth_codes"


class AppAccessToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    app_slug = models.CharField(max_length=40)
    social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="app_access_tokens",
    )
    token = models.CharField(max_length=80)
    created_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "app_access_tokens"
