"""FB 2010 Places + Questions — unmanaged models (ensured on deploy)."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class Place(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=120, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    osm_type = models.CharField(max_length=20, blank=True, default="")
    osm_id = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, null=True, blank=True,
        related_name="+", db_column="created_by_id",
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "places"
        ordering = ["name"]

    def get_absolute_url(self):
        return f"/places/{self.pk}"

    @property
    def photo_url(self):
        from apps.social.media import media_url
        return media_url(self.photo_path)


class PlaceCheckin(models.Model):
    id = models.BigAutoField(primary_key=True)
    place = models.ForeignKey(Place, models.DO_NOTHING, related_name="checkins")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="checkins")
    message = models.CharField(max_length=500, blank=True, default="")
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "place_checkins"
        ordering = ["-id"]

    @property
    def photo_url(self):
        from apps.social.media import media_url
        return media_url(self.photo_path)


class Question(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="questions")
    body = models.CharField(max_length=500)
    photo_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "questions"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/questions/{self.pk}"

    @property
    def photo_url(self):
        from apps.social.media import media_url
        return media_url(self.photo_path)


class QuestionAnswer(models.Model):
    id = models.BigAutoField(primary_key=True)
    question = models.ForeignKey(Question, models.DO_NOTHING, related_name="answers")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="question_answers")
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "question_answers"
        ordering = ["id"]


class QuestionVote(models.Model):
    id = models.BigAutoField(primary_key=True)
    answer = models.ForeignKey(QuestionAnswer, models.DO_NOTHING, related_name="votes")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="question_votes")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "question_votes"


class PlaceReview(models.Model):
    """FB Places reviews — stars + short text (2010)."""
    id = models.BigAutoField(primary_key=True)
    place = models.ForeignKey(Place, models.DO_NOTHING, related_name="reviews")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="place_reviews")
    stars = models.SmallIntegerField(default=5)
    body = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "place_reviews"
        ordering = ["-id"]


class ClassicPoll(models.Model):
    """Classic FB Polls — separate from banned models/polls.py path."""
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="classic_polls")
    question = models.CharField(max_length=500)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "classic_polls"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/polls/{self.pk}"


class ClassicPollOption(models.Model):
    id = models.BigAutoField(primary_key=True)
    poll = models.ForeignKey(ClassicPoll, models.DO_NOTHING, related_name="options")
    body = models.CharField(max_length=255)
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "classic_poll_options"
        ordering = ["sort_order", "id"]


class ClassicPollVote(models.Model):
    id = models.BigAutoField(primary_key=True)
    poll = models.ForeignKey(ClassicPoll, models.DO_NOTHING, related_name="votes")
    option = models.ForeignKey(ClassicPollOption, models.DO_NOTHING, related_name="votes")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="classic_poll_votes")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "classic_poll_votes"
