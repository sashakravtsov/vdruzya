"""Unmanaged tables — classic FB 2009 Likes + post tags + group docs."""
from __future__ import annotations

from django.db import models

from .feed import Comment, Post
from .groups import Community
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


class CommentReaction(models.Model):
    """FB 2009 Like on wall comments."""
    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(Comment, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "comment_reactions"


class PostTag(models.Model):
    """Tag a friend on a wall post (classic «с:»)."""
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(Post, models.DO_NOTHING, related_name="person_tags")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="wall_post_tags")
    tagged_by = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="wall_post_tags_made",
        db_column="tagged_by_id",
    )
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "post_tags"
        ordering = ["id"]


class GroupDoc(models.Model):
    """Classic FB Group Docs."""
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(Community, models.DO_NOTHING, related_name="docs")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="group_docs")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "classic_group_docs"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/groups/{self.community_id}/docs/{self.pk}"
