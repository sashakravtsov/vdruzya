from django.contrib import admin
from apps.social.models import Community, SocialProfile


@admin.register(SocialProfile)
class SocialProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "city")
    search_fields = ("name", "slug", "city")
    list_select_related = ("user",)
    readonly_fields = ("id", "user", "created_at", "updated_at")
    exclude = ("cover_path", "pronouns", "life_goals", "family_status", "district", "verified")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "privacy", "join_mode")
    search_fields = ("name", "slug")
    list_select_related = ("creator",)
