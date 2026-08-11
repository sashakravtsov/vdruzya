from __future__ import annotations
from django.db import models
from .feed import Post
from .groups import CommunityPost
from .people import SocialProfile


class PostPoll(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.OneToOneField(Post, models.DO_NOTHING, related_name="poll")
    allows_multiple = models.BooleanField(default=False)
    votes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "post_polls"


class PollOption(models.Model):
    id = models.BigAutoField(primary_key=True)
    poll = models.ForeignKey(PostPoll, models.DO_NOTHING, related_name="options", db_column="post_poll_id")
    label = models.CharField(max_length=255)
    sort_order = models.SmallIntegerField(default=0)
    votes_count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "poll_options"
        ordering = ["sort_order", "id"]


class PollVote(models.Model):
    id = models.BigAutoField(primary_key=True)
    option = models.ForeignKey(PollOption, models.DO_NOTHING, related_name="votes", db_column="poll_option_id")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="poll_votes")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poll_votes"


class CommunityPostPoll(models.Model):
    id = models.BigAutoField(primary_key=True)
    post = models.OneToOneField(
        CommunityPost, models.DO_NOTHING, related_name="poll", db_column="community_post_id"
    )
    allows_multiple = models.BooleanField(default=False)
    votes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_post_polls"


class CommunityPollOption(models.Model):
    id = models.BigAutoField(primary_key=True)
    poll = models.ForeignKey(
        CommunityPostPoll, models.DO_NOTHING, related_name="options", db_column="community_post_poll_id"
    )
    label = models.CharField(max_length=255)
    sort_order = models.SmallIntegerField(default=0)
    votes_count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "community_poll_options"
        ordering = ["sort_order", "id"]


class CommunityPollVote(models.Model):
    id = models.BigAutoField(primary_key=True)
    option = models.ForeignKey(
        CommunityPollOption, models.DO_NOTHING, related_name="votes", db_column="community_poll_option_id"
    )
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="community_poll_votes")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "community_poll_votes"
