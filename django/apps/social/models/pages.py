"""Facebook Pages — classic chrome on legacy `companies` tables."""
from __future__ import annotations

from django.db import models

from .people import SocialProfile


class Company(models.Model):
    """Public Page (Страница) — FB Pages surface, 2006 chrome."""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=255, default="other")
    city = models.CharField(max_length=255, blank=True, default="")
    size = models.CharField(max_length=255, blank=True, default="")
    cover_color = models.CharField(max_length=255, default="#3B5998")
    cover_path = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "companies"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("pages.show", kwargs={"pk": self.pk})

    @property
    def topic_key(self) -> str:
        return f"page:{self.id}"

    @property
    def cover_url(self) -> str | None:
        from apps.social.media import media_url
        return media_url(self.cover_path)


class CompanyAdmin(models.Model):
    id = models.BigAutoField(primary_key=True)
    company = models.ForeignKey(Company, models.DO_NOTHING, related_name="admins")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="page_admins")
    role = models.CharField(max_length=255, default="admin")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "company_admins"


class CompanyFollower(models.Model):
    id = models.BigAutoField(primary_key=True)
    company = models.ForeignKey(Company, models.DO_NOTHING, related_name="followers")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="page_follows")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "company_followers"
