"""Classic Facebook inbox — DMs, group chats, broadcast, notifications."""
from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404

from apps.social.friendship import is_blocked
from apps.social.models import Conversation, ConversationMember, Message, Notification, SocialProfile, Sticker
from apps.social.services import friend_ids, now


def is_member(me, conversation_id) -> bool:
    return bool(
        me
        and ConversationMember.objects.filter(conversation_id=conversation_id, social_user=me).exists()
    )


def require_member(me, conversation_id) -> Conversation:
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not is_member(me, conv.id):
        raise Http404("not a member")
    return conv


def peer(conv: Conversation, me) -> SocialProfile | None:
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


def leave(me, conv: Conversation):
    ConversationMember.objects.filter(conversation=conv, social_user=me).delete()
    cache.delete(f"nav:{me.id}")


def _invalidate_members(conv_id):
    for pid in ConversationMember.objects.filter(conversation_id=conv_id).values_list("social_user_id", flat=True):
        cache.delete(f"nav:{pid}")


def inbox(me, limit=40, q="", unread_only=False):
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
        .distinct()
    )
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(members__social_user__name__icontains=q)
        ).distinct()

    rows = list(qs[: limit * 2 if q or unread_only else limit])
    my_read = {
        row.conversation_id: row.last_read_at
        for row in ConversationMember.objects.filter(social_user=me, conversation_id__in=[c.id for c in rows])
    }
    out = []
    for c in rows:
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
        if unread_only and not c.unread:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def thread(conv: Conversation, before_id=None, limit=50):
    """Messages oldest→newest. `before` expands the window upward (keeps recent)."""
    qs = Message.objects.filter(conversation=conv).select_related("social_user")
    if before_id:
        bid = int(before_id)
        older = list(qs.filter(id__lt=bid).order_by("-id")[:limit])
        start = older[-1].id if older else bid
        rows = list(qs.filter(id__gte=start).order_by("id")[:500])
        has_older = bool(older) and Message.objects.filter(conversation=conv, id__lt=start).exists()
        return rows, has_older
    rows = list(qs.order_by("-id")[:limit])
    rows.reverse()
    has_older = bool(rows) and Message.objects.filter(conversation=conv, id__lt=rows[0].id).exists()
    return rows, has_older


def can_dm(me, other: SocialProfile) -> str | None:
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


def notify_peers(me, conv: Conversation, m: Message):
    peer_ids = list(
        ConversationMember.objects.filter(conversation=conv)
        .exclude(social_user=me)
        .values_list("social_user_id", flat=True)
    )
    if not peer_ids:
        return
    t = now()
    snippet = (m.body or "")[:120]
    title = "Новое сообщение"
    Notification.objects.bulk_create([
        Notification(
            social_user_id=pid,
            title=title,
            body=f"{me.name}: {snippet}"[:255],
            seen=False,
            type="message",
            url=f"/messenger?c={conv.id}",
            created_at=t,
        )
        for pid in peer_ids
    ])
    for pid in peer_ids:
        cache.delete(f"nav:{pid}")


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
    notify_peers(me, conv, m)
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


def wants_json(request) -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def json_message(m: Message):
    return JsonResponse(ws_payload(m))


def after_send(m: Message):
    transaction.on_commit(lambda: broadcast(m))
