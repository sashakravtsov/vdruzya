from django.contrib import admin
from apps.accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "name", "created_at", "last_login")
    search_fields = ("email", "name")
    readonly_fields = ("id", "password", "created_at", "updated_at", "last_login")
