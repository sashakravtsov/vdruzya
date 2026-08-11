from __future__ import annotations
from django.db import models
from .people import SocialProfile

class Conversation(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    community_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "conversations"

class ConversationMember(models.Model):
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, models.DO_NOTHING, related_name="members")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="conversations")
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "conversation_members"

class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, models.DO_NOTHING, related_name="messages")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="messages")
    body = models.TextField()
    message_type = models.CharField(max_length=255, default="text")
    sticker_id = models.BigIntegerField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "messages"
        ordering = ["id"]

class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="notifications")
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=255)
    seen = models.BooleanField(default=False)
    type = models.CharField(max_length=255)
    url = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "notifications"
        ordering = ["-id"]

class StickerPack(models.Model):
    id = models.BigAutoField(primary_key=True)
    slug = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "sticker_packs"

class Sticker(models.Model):
    id = models.BigAutoField(primary_key=True)
    pack = models.ForeignKey(StickerPack, models.DO_NOTHING, related_name="stickers", db_column="sticker_pack_id")
    slug = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    phrase = models.CharField(max_length=255, null=True, blank=True)
    background_color = models.CharField(max_length=32, default="#e8f3ff")
    foreground_color = models.CharField(max_length=32, default="#2f6fed")
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "stickers"
        ordering = ["sort_order", "id"]

