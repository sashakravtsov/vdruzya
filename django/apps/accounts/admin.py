from django.contrib import admin
from apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "name", "is_staff", "is_superuser", "created_at", "last_login")
    search_fields = ("email", "name")
    list_filter = ("is_staff", "is_superuser")
    readonly_fields = ("id", "password", "created_at", "updated_at", "last_login")
    fields = (
        "id", "email", "name", "is_staff", "is_superuser",
        "phone", "email_verified_at", "last_login", "created_at", "updated_at", "password",
    )
