"""FB 2013 classic modules — Hashtags."""
from __future__ import annotations

from django.db import models

from .feed import Post


class Hashtag(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "hashtags"
        ordering = ["name"]

    def get_absolute_url(self):
        return f"/hashtag/{self.name}"


class PostHashtag(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="hashtag_links")
    hashtag = models.ForeignKey(Hashtag, models.DO_NOTHING, related_name="post_links")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "post_hashtags"
        ordering = ["-id"]
