"""Unmanaged tables for orphan cleanup only — not Facebook 2006 product surface."""
from __future__ import annotations

from django.db import models

from .feed import Post
from .people import SocialProfile


class Reaction(models.Model):
    """Legacy likes (FB 2009+) — delete with posts; never expose in UI."""
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "reactions"
