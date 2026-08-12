"""Unmanaged tables — classic FB 2009 Likes + post tags + group docs + relationship."""
from __future__ import annotations

from django.db import models

from .feed import Comment, Post
from .groups import Community, CommunityPost, CommunityPostComment
from .more import Photo, PhotoComment
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


class PhotoCommentReaction(models.Model):
    """Like on photo comments."""
    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(PhotoComment, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "photo_comment_reactions"


class GroupCommentReaction(models.Model):
    """Like on group wall/discussion comments."""
    id = models.BigAutoField(primary_key=True)
    comment = models.ForeignKey(CommunityPostComment, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "group_comment_reactions"


class GroupPostReaction(models.Model):
    """Like on group wall/discussion posts."""
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(CommunityPost, models.DO_NOTHING, related_name="+")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    type = models.CharField(max_length=255, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "group_post_reactions"


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


class RelationshipRequest(models.Model):
    """Pending confirmation when A lists B as partner."""
    id = models.BigAutoField(primary_key=True)
    requester = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="relationship_sent",
        db_column="requester_id",
    )
    partner = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="relationship_received",
        db_column="partner_id",
    )
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "relationship_requests"
        ordering = ["-id"]


class FeedHide(models.Model):
    """Hide all News Feed stories from an actor."""
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    actor = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="+", db_column="actor_id",
    )
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "feed_hides"


class FeedStoryHide(models.Model):
    """Hide one News Feed story key (kind:id)."""
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="+")
    story_key = models.CharField(max_length=80)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "feed_story_hides"


class FamilyLink(models.Model):
    """Classic FB Family member (pending until confirmed)."""
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="+", db_column="from_user_id",
    )
    to_user = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, related_name="+", db_column="to_user_id",
    )
    kind = models.CharField(max_length=20, default="sibling")
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "family_links"
        ordering = ["id"]

    @property
    def kind_label(self) -> str:
        from apps.social.family import label
        return label(self.kind)
