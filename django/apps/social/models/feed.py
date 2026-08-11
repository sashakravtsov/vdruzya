from __future__ import annotations
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from .people import SocialProfile

class Post(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="posts")
    visibility = models.CharField(max_length=255, default="public")
    kind = models.CharField(max_length=255, default="text")
    body = models.TextField()
    topic = models.CharField(max_length=255, blank=True, default="thought")
    mood = models.CharField(max_length=255, null=True, blank=True)
    emoji = models.CharField(max_length=16, null=True, blank=True)
    sticker = models.CharField(max_length=255, null=True, blank=True)
    media_path = models.CharField(max_length=255, null=True, blank=True)
    media_label = models.CharField(max_length=255, null=True, blank=True)
    shared_post = models.ForeignKey(
        "self", models.DO_NOTHING, null=True, blank=True, related_name="shares", db_column="shared_post_id"
    )
    search_vector = SearchVectorField(null=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "posts"
        ordering = ["-id"]

    @property
    def media_url(self):
        from apps.social.media import media_url
        return media_url(self.media_path)


class PostMedia(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="media")
    path = models.CharField(max_length=255)
    photo_id = models.BigIntegerField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "post_media"

    @property
    def url(self):
        from apps.social.media import media_url
        return media_url(self.path)

class Comment(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="comments")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="comments")
    body = models.TextField()
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "comments"
        ordering = ["id"]

class Reaction(models.Model):
    """Legacy likes table (FB 2009+) — kept unmanaged for orphan cleanup only."""
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="reactions")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="reactions")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "reactions"

