"""FB 2010 Places + Questions — unmanaged models (ensured on deploy)."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class Place(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=120, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "places"
        ordering = ["name"]

    def get_absolute_url(self):
        return f"/places/{self.pk}"


class PlaceCheckin(models.Model):
    id = models.BigAutoField(primary_key=True)
    place = models.ForeignKey(Place, models.DO_NOTHING, related_name="checkins")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="checkins")
    message = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "place_checkins"
        ordering = ["-id"]


class Question(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="questions")
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "questions"
        ordering = ["-id"]

    def get_absolute_url(self):
        return f"/questions/{self.pk}"


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
