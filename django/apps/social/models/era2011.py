"""FB 2011 classic modules — Subscribe, Timeline milestones, Open Graph stories."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class ProfileFollow(models.Model):
    """Public Subscribe/Follow without friendship (FB 2011)."""
    id = models.BigAutoField(primary_key=True)
    follower = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="following",
        db_column="follower_id",
    )
    followee = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="followers",
        db_column="followee_id",
    )
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "profile_follows"
        ordering = ["-id"]


class TimelineMilestone(models.Model):
    """Classic Timeline milestone (life event) under 2006 chrome."""
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="milestones",
    )
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=500, blank=True, default="")
    kind = models.CharField(max_length=40, default="life")
    occurred_on = models.DateField()
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "timeline_milestones"
        ordering = ["-occurred_on", "-id"]


class OgStory(models.Model):
    """Open Graph activity — listening / reading / watching."""
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="og_stories",
    )
    verb = models.CharField(max_length=32)
    object_title = models.CharField(max_length=255)
    object_url = models.CharField(max_length=255, blank=True, default="")
    app_slug = models.CharField(max_length=40, default="custom")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "og_stories"
        ordering = ["-id"]
