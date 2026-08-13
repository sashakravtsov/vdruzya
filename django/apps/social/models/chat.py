from __future__ import annotations
from django.db import models
from .people import SocialProfile


class Conversation(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    community_id = models.BigIntegerField(null=True, blank=True)
    community_peer_id = models.BigIntegerField(null=True, blank=True)
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
    archived_at = models.DateTimeField(null=True, blank=True)
    muted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "conversation_members"


class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, models.DO_NOTHING, related_name="messages")
    social_user = models.ForeignKey(SocialProfile, models.DO_NOTHING, related_name="messages")
    body = models.TextField(blank=True, default="")
    message_type = models.CharField(max_length=255, default="text")
    sticker_id = models.BigIntegerField(null=True, blank=True)
    reply_to = models.ForeignKey(
        "self", models.DO_NOTHING, null=True, blank=True, related_name="replies", db_column="reply_to_id",
    )
    attachment_path = models.CharField(max_length=255, null=True, blank=True)
    attachment_disk = models.CharField(max_length=255, null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)
    attachment_mime = models.CharField(max_length=255, null=True, blank=True)
    # Telegram-style voice waveform peaks ("12,40,88,...") + duration for classic player
    waveform = models.CharField(max_length=512, null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "messages"
        ordering = ["id"]

    @property
    def attachment_url(self):
        from apps.social.media import media_url
        return media_url(self.attachment_path)

    @property
    def attachment_is_video(self) -> bool:
        if (self.message_type or "") == "video":
            return True
        return (self.attachment_mime or "").startswith("video/")

    @property
    def attachment_is_audio(self) -> bool:
        if (self.message_type or "") == "voice":
            return True
        return (self.attachment_mime or "").lower().startswith("audio/")

    @property
    def body_visible(self) -> bool:
        """Hide placeholder bodies for media/sticker/voice lines."""
        b = (self.body or "").strip()
        if not b:
            return False
        if b in ("[фото]", "[видео]", "[стикер]", "[голосовое]"):
            return False
        if b.startswith("[голосовое "):
            return False
        return True

    @property
    def waveform_bars(self) -> list[int]:
        from apps.social.media import parse_waveform_peaks
        peaks = parse_waveform_peaks(self.waveform)
        if peaks:
            return peaks
        # Soft placeholder so older voice notes still read as a track
        return [18 + ((i * 17 + (self.id or 0) * 3) % 62) for i in range(40)]

    @property
    def duration_label(self) -> str:
        from apps.social.media import format_duration_ms
        return format_duration_ms(self.duration_ms)


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

