"""Classic Facebook inbox helpers — DMs, group chats, broadcast."""
from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models import Count, F, OuterRef, Prefetch, Subquery
from django.shortcuts import get_object_or_404

from apps.social.friendship import friends_of, is_blocked
from apps.social.models import Conversation, ConversationMember, Message, SocialProfile, Sticker
from apps.social.services import friend_ids, now


def is_member(me, conversation_id) -> bool:
    return bool(
        me
        and ConversationMember.objects.filter(conversation_id=conversation_id, social_user=me).exists()
    )


def require_member(me, conversation_id) -> Conversation:
    from django.http import Http404
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not is_member(me, conv.id):
        raise Http404("not a member")
    return conv


def peer(conv: Conversation, me) -> SocialProfile | None:
    """Other member in a 1:1 DM; None for group chats."""
    if conv.community_id:
        return None
    for m in conv.members.all():
        if m.social_user_id != me.id:
            return m.social_user
    return None


def label(conv: Conversation, me) -> str:
    if conv.title:
        return conv.title
    other = peer(conv, me)
    return other.name if other else f"Диалог #{conv.id}"


def mark_read(me, conv: Conversation):
    ConversationMember.objects.filter(conversation=conv, social_user=me).update(last_read_at=now())
    cache.delete(f"nav:{me.id}")


def _invalidate_members(conv_id, except_id=None):
    ids = ConversationMember.objects.filter(conversation_id=conv_id).values_list("social_user_id", flat=True)
    for pid in ids:
        if except_id is None or pid != except_id:
            cache.delete(f"nav:{pid}")
    if except_id:
        cache.delete(f"nav:{except_id}")


def inbox(me, limit=40):
    """Conversations for sidebar: peer/title, last message, unread."""
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    qs = (
        Conversation.objects.filter(members__social_user=me)
        .annotate(
            last_body=Subquery(last.values("body")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            last_type=Subquery(last.values("message_type")[:1]),
            last_from_id=Subquery(last.values("social_user_id")[:1]),
        )
        .prefetch_related(
            Prefetch(
                "members",
                queryset=ConversationMember.objects.select_related("social_user"),
            )
        )
        .order_by(F("updated_at").desc(nulls_last=True), "-id")
        .distinct()[:limit]
    )
    my_read = {
        row.conversation_id: row.last_read_at
        for row in ConversationMember.objects.filter(social_user=me, conversation__in=qs)
    }
    out = []
    for c in qs:
        c.display_name = label(c, me)
        c.peer = peer(c, me)
        c.snippet = (c.last_body or "")[:80]
        if c.last_type == "sticker" and c.snippet:
            c.snippet = f"[стикер] {c.snippet}"
        read_at = my_read.get(c.id)
        c.unread = bool(
            c.last_from_id
            and c.last_from_id != me.id
            and c.last_at
            and (read_at is None or c.last_at > read_at)
        )
        out.append(c)
    return out


def thread(conv: Conversation, before_id=None, limit=50):
    """Newest `limit` messages (or older than before_id), returned oldest→newest."""
    qs = Message.objects.filter(conversation=conv).select_related("social_user")
    if before_id:
        qs = qs.filter(id__lt=int(before_id))
    rows = list(qs.order_by("-id")[:limit])
    rows.reverse()
    has_older = bool(rows) and Message.objects.filter(conversation=conv, id__lt=rows[0].id).exists()
    return rows, has_older


def can_dm(me, other: SocialProfile) -> str | None:
    """Return error text, or None if OK."""
    if not me or me.id == other.id:
        return "Нельзя написать себе."
    if is_blocked(me, other):
        return "Переписка недоступна."
    if other.id not in friend_ids(me):
        return "Писать можно только друзьям."
    return None


def dm_find_or_create(me, other: SocialProfile) -> Conversation:
    shared = (
        Conversation.objects.filter(community_id__isnull=True)
        .filter(members__social_user=me)
        .filter(members__social_user=other)
        .annotate(n=Count("members", distinct=True))
        .filter(n=2)
        .order_by("id")
        .first()
    )
    if shared:
        return shared
    t = now()
    conv = Conversation.objects.create(created_at=t, updated_at=t)
    ConversationMember.objects.bulk_create([
        ConversationMember(conversation=conv, social_user=me),
        ConversationMember(conversation=conv, social_user=other),
    ])
    return conv


def post_message(me, conv: Conversation, body: str, *, message_type="text", sticker_id=None) -> Message:
    body = (body or "").strip()
    if not body:
        raise ValueError("empty")
    t = now()
    m = Message.objects.create(
        conversation=conv,
        social_user=me,
        body=body[:4000],
        message_type=message_type,
        sticker_id=sticker_id,
        created_at=t,
    )
    Conversation.objects.filter(pk=conv.pk).update(updated_at=t)
    _invalidate_members(conv.id)
    return m


def post_sticker(me, conv: Conversation, sticker: Sticker) -> Message:
    return post_message(
        me, conv, sticker.phrase or sticker.title,
        message_type="sticker", sticker_id=sticker.id,
    )


def ws_payload(m: Message) -> dict:
    return {
        "type": "chat.message",
        "id": m.id,
        "body": m.body,
        "name": m.social_user.name,
        "user_id": m.social_user_id,
        "message_type": m.message_type or "text",
    }


def broadcast(m: Message):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(f"chat_{m.conversation_id}", ws_payload(m))
