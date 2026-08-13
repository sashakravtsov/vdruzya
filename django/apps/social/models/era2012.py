"""FB 2012 classic modules — Page Timeline milestones + Collections."""
from __future__ import annotations

from django.db import models

from .pages import Company
from .people import SocialProfile
from .feed import Post


class PageTimelineMilestone(models.Model):
    id = models.BigAutoField(primary_key=True)
    company = models.ForeignKey(Company, models.DO_NOTHING, related_name="milestones")
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=500, blank=True, default="")
    kind = models.CharField(max_length=40, default="life")
    occurred_on = models.DateField()
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "page_timeline_milestones"
        ordering = ["-occurred_on", "-id"]


class Collection(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="collections",
    )
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=500, blank=True, default="")
    visibility = models.CharField(max_length=20, default="friends")
    cover_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "collections"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/collections/{self.pk}"

    @property
    def cover_url(self) -> str | None:
        from apps.social.media import media_url
        return media_url(self.cover_path)


class CollectionItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    collection = models.ForeignKey(Collection, models.DO_NOTHING, related_name="items")
    kind = models.CharField(max_length=20)
    post = models.ForeignKey(
        Post, models.DO_NOTHING, null=True, blank=True, related_name="+",
    )
    company = models.ForeignKey(
        Company, models.DO_NOTHING, null=True, blank=True, related_name="+",
    )
    url = models.CharField(max_length=500, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="")
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "collection_items"
        ordering = ["position", "id"]
