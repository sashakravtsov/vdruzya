"""Unmanaged tables — Reaction powers classic FB 2009 Likes."""
from __future__ import annotations

from django.db import models

from .feed import Post
from .more import Photo
from .people import SocialProfile


class Reaction(models.Model):
    """FB 2009 Like — type=like on wall notes / posts."""
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "reactions"


class PhotoReaction(models.Model):
    """FB 2009 Photo Like — separate from post reactions."""
    id = models.BigAutoField(primary_key=True)
    photo = models.ForeignKey(Photo, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "photo_reactions"
