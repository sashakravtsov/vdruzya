"""FB 2014 classic modules — Save + Safety Check."""
from __future__ import annotations

from django.db import models

from .era2010 import Place
from .feed import Post
from .more import Event
from .pages import Company
from .people import SocialProfile


class SavedItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="saved_items")
    kind = models.CharField(max_length=20, default="post")
    post = models.ForeignKey(Post, models.DO_NOTHING, null=True, blank=True, related_name="+")
    company = models.ForeignKey(Company, models.DO_NOTHING, null=True, blank=True, related_name="+")
    event = models.ForeignKey(Event, models.DO_NOTHING, null=True, blank=True, related_name="+")
    place = models.ForeignKey(Place, models.DO_NOTHING, null=True, blank=True, related_name="+")
    url = models.CharField(max_length=500, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "saved_items"
        ordering = ["-id"]

    def get_absolute_url(self):
        if self.post_id:
            return f"/posts/{self.post_id}"
        if self.company_id:
            return f"/pages/{self.company_id}"
        if self.event_id:
            return f"/events/{self.event_id}"
        if self.place_id:
            return f"/places/{self.place_id}"
        return self.url or "/saves"


class SafetyEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True, default="")
    body = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    radius_km = models.FloatField(default=50)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "safety_events"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/safety/{self.id}"


class SafetyCheckin(models.Model):
    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(SafetyEvent, models.DO_NOTHING, related_name="checkins")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="safety_checkins")
    status = models.CharField(max_length=20, default="safe")
    marked_by = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "safety_checkins"
        ordering = ["-id"]
