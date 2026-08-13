"""Extra classic FB modules — lists + marketplace (unmanaged; ensured on deploy)."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class FriendList(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="friend_lists")
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "friend_lists"
        ordering = ["name"]

    def get_absolute_url(self):
        return f"/friends/lists/{self.pk}"


class FriendListMember(models.Model):
    id = models.BigAutoField(primary_key=True)
    friend_list = models.ForeignKey(FriendList, models.DO_NOTHING, related_name="memberships")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="list_memberships")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "friend_list_members"


class MarketplaceListing(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="market_listings")
    title = models.CharField(max_length=160)
    price = models.CharField(max_length=40, blank=True, default="")
    place = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "marketplace_listings"
        ordering = ["-id"]

    @property
    def photo_url(self):
        from apps.social.media import media_url
        return media_url(self.photo_path)

    def get_absolute_url(self):
        return f"/marketplace/{self.pk}"
