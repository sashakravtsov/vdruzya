from __future__ import annotations
from django.db import models
from .people import SocialProfile

class Community(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=255)
    description = models.TextField()
    cover_color = models.CharField(max_length=255, default="#243b55")
    cover_path = models.CharField(max_length=255, null=True, blank=True)
    short_description = models.CharField(max_length=200, null=True, blank=True)
    privacy = models.CharField(max_length=255, default="public")
    join_mode = models.CharField(max_length=40, default="open")
    posting_policy = models.CharField(max_length=40, default="members")
    messaging_enabled = models.BooleanField(default=True)
    creator = models.ForeignKey(SocialProfile, models.DO_NOTHING, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "communities"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("groups.show", kwargs={"pk": self.pk})

    @property
    def cover_url(self):
        from apps.social.media import media_url
        return media_url(self.cover_path)

class CommunityMember(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(Community, models.DO_NOTHING, related_name="memberships")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="memberships")
    role = models.CharField(max_length=255)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_members"

class CommunityPost(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(Community, models.DO_NOTHING, related_name="posts")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="community_posts")
    body = models.TextField()
    kind = models.CharField(max_length=40, default="text")
    topic = models.CharField(max_length=40, default="discussion")
    media_path = models.CharField(max_length=255, null=True, blank=True)
    posted_as_community = models.BooleanField(default=False)
    sticker = models.CharField(max_length=255, null=True, blank=True)
    emoji = models.CharField(max_length=40, null=True, blank=True)
    mood = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_posts"
        ordering = ["-id"]

    @property
    def media_url(self):
        from apps.social.media import media_url
        return media_url(self.media_path)

    @property
    def title_line(self) -> str:
        line = (self.body or "").strip().split("\n", 1)[0].strip()
        if not line:
            return "Фото" if self.kind == "photo" or self.media_path else ("Опрос" if self.kind == "poll" else "Тема")
        return line[:80] + ("…" if len(line) > 80 else "")

    def get_absolute_url(self):
        base = f"/groups/{self.community_id}"
        if self.topic == "wall":
            return f"{base}#topic-{self.id}"
        return f"{base}?topic={self.id}#board"

    @property
    def sticker_url(self):
        if not self.sticker:
            return ""
        if "://" in self.sticker:
            return self.sticker
        from apps.social.media import media_url
        return media_url(self.sticker) or self.sticker


class CommunityPostMedia(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(CommunityPost, models.DO_NOTHING, related_name="media", db_column="community_post_id")
    path = models.CharField(max_length=255)
    photo_id = models.BigIntegerField(null=True, blank=True)
    sort_order = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_post_media"
        ordering = ["sort_order", "id"]

    @property
    def url(self):
        from apps.social.media import media_url
        return media_url(self.path)


class CommunityPostComment(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(CommunityPost, models.DO_NOTHING, related_name="comments", db_column="community_post_id")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="community_comments")
    body = models.TextField()
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_post_comments"

class CommunityPostReaction(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(CommunityPost, models.DO_NOTHING, related_name="reactions", db_column="community_post_id")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="community_reactions")
    type = models.CharField(max_length=40, default="like")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_post_reactions"

class CommunityJoinRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    community = models.ForeignKey(Community, models.DO_NOTHING, related_name="join_requests")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="join_requests")
    status = models.CharField(max_length=40, default="pending")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_join_requests"

