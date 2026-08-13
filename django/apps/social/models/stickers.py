"""Sticker catalog — reused as classic FB Gifts (no separate gifts table)."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class StickerPack(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner_social_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, null=True, blank=True, related_name="sticker_packs",
    )
    slug = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, default="")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "sticker_packs"

    def __str__(self):
        return self.title


class Sticker(models.Model):
    """Catalog item shown as a Gift in classic chrome."""
    id = models.BigAutoField(primary_key=True)
    sticker_pack = models.ForeignKey(StickerPack, models.DO_NOTHING, related_name="stickers")
    slug = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    phrase = models.CharField(max_length=255, blank=True, default="")
    image_path = models.CharField(max_length=255, null=True, blank=True)
    image_disk = models.CharField(max_length=255, null=True, blank=True)
    background_color = models.CharField(max_length=40, null=True, blank=True)
    foreground_color = models.CharField(max_length=40, null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "stickers"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title

    @property
    def bg(self) -> str:
        return (self.background_color or "#3B5998").strip() or "#3B5998"

    @property
    def fg(self) -> str:
        return (self.foreground_color or "#FFFFFF").strip() or "#FFFFFF"

    @property
    def image_url(self) -> str:
        if not self.image_path:
            return ""
        from apps.social.media import media_url
        return media_url(self.image_path) or ""
