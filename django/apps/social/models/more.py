from __future__ import annotations

from django.db import models
from django.db.models import OuterRef, Subquery

from .groups import Community
from .pages import Company
from .people import SocialProfile


class AlbumQuerySet(models.QuerySet):
    def visible_to(self, viewer):
        from apps.social.albums import visible_q
        return self.filter(visible_q(viewer))

    def with_covers(self):
        first = (
            Photo.objects.filter(album_id=OuterRef("pk"))
            .exclude(path="")
            .order_by("id")
            .values("path")[:1]
        )
        return self.annotate(_first_photo_path=Subquery(first))


class Album(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="albums")
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    visibility = models.CharField(max_length=20, default="friends")
    cover_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    objects = AlbumQuerySet.as_manager()

    class Meta:
        managed = False
        db_table = "albums"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("albums.show", kwargs={"album_id": self.pk})

    @property
    def cover_url(self):
        from apps.social.media import media_url
        path = self.cover_path or getattr(self, "_first_photo_path", None)
        return media_url(path) if path else ""


class Photo(models.Model):
    id = models.BigAutoField(primary_key=True)
    album = models.ForeignKey(Album, models.DO_NOTHING, related_name="photos")
    title = models.CharField(max_length=255)
    path = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, default="#dbeafe")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "photos"

    @property
    def url(self):
        from apps.social.media import media_url
        return media_url(self.path)


class PhotoComment(models.Model):
    id = models.BigAutoField(primary_key=True)
    photo = models.ForeignKey(Photo, models.DO_NOTHING, related_name="comments")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="photo_comments")
    body = models.TextField()
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "photo_comments"
        ordering = ["id"]


class Event(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    place = models.CharField(max_length=255, default="")
    description = models.TextField(default="", blank=True)
    starts_at = models.DateTimeField()
    host = models.ForeignKey(
        SocialProfile, models.DO_NOTHING, null=True, blank=True, related_name="hosted_events",
    )
    community = models.ForeignKey(Community, models.DO_NOTHING, null=True, blank=True)
    # Page-hosted events (nullable; ensured via deploy ALTER IF NOT EXISTS)
    company = models.ForeignKey(
        Company, models.DO_NOTHING, null=True, blank=True, related_name="events",
        db_column="company_id",
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "events"
        ordering = ["starts_at"]

    def get_absolute_url(self):
        return f"/events/{self.pk}"


class EventAttendee(models.Model):
    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(Event, models.DO_NOTHING, related_name="attendees")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="event_rsvps")
    status = models.CharField(max_length=40, default="going")  # going | maybe | declined
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "event_attendees"
