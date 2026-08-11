"""Classic Facebook inbox — DMs, group chats, attachments, broadcast."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404

from apps.social.friendship import is_blocked
from apps.social.media import save_image
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
    others = [m.social_user for m in conv.members.all() if m.social_user_id != me.id]
    if conv.community_id or len(others) != 1:
        return None
    return others[0]


def others(conv: Conversation, me) -> list[SocialProfile]:
    return [m.social_user for m in conv.members.all() if m.social_user_id != me.id]


def label(conv: Conversation, me) -> str:
    if conv.title:
        return conv.title
    peeps = others(conv, me)
    if len(peeps) == 1:
        return peeps[0].name
    if peeps:
        return ", ".join(p.name for p in peeps[:3]) + ("…" if len(peeps) > 3 else "")
    return f"Диалог #{conv.id}"


def mark_read(me, conv: Conversation):
    ConversationMember.objects.filter(conversation=conv, social_user=me).update(last_read_at=now())
    cache.delete(f"nav:{me.id}")


def mark_unread(me, conv: Conversation):
    last = (
        Message.objects.filter(conversation=conv)
        .exclude(social_user=me)
        .order_by("-id")
        .only("created_at")
        .first()
    )
    t = (last.created_at - timedelta(seconds=1)) if last and last.created_at else None
    ConversationMember.objects.filter(conversation=conv, social_user=me).update(last_read_at=t)
    cache.delete(f"nav:{me.id}")


def leave(me, conv: Conversation):
    ConversationMember.objects.filter(conversation=conv, social_user=me).delete()
    cache.delete(f"nav:{me.id}")


def _invalidate_members(conv_id):
    for pid in ConversationMember.objects.filter(conversation_id=conv_id).values_list("social_user_id", flat=True):
        cache.delete(f"nav:{pid}")


def _revive_dm(conv: Conversation, me):
    if conv.community_id:
        return
    past = set(Message.objects.filter(conversation=conv).values_list("social_user_id", flat=True))
    past.add(me.id)
    if len(past) > 2:
        return
    have = set(ConversationMember.objects.filter(conversation=conv).values_list("social_user_id", flat=True))
    for pid in past - have:
        ConversationMember.objects.create(conversation=conv, social_user_id=pid)


def inbox(me, limit=40, q="", unread_only=False, sent_only=False):
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    qs = (
        Conversation.objects.filter(members__social_user=me)
        .annotate(
            last_body=Subquery(last.values("body")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            last_type=Subquery(last.values("message_type")[:1]),
            last_from_id=Subquery(last.values("social_user_id")[:1]),
            last_attach=Subquery(last.values("attachment_path")[:1]),
        )
        .prefetch_related(
            Prefetch("members", queryset=ConversationMember.objects.select_related("social_user"))
        )
        .order_by(F("updated_at").desc(nulls_last=True), "-id")
        .distinct()
    )
    q = (q or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(members__social_user__name__icontains=q)).distinct()

    rows = list(qs[: limit * 3 if (q or unread_only or sent_only) else limit])
    my_read = {
        row.conversation_id: row.last_read_at
        for row in ConversationMember.objects.filter(social_user=me, conversation_id__in=[c.id for c in rows])
    }
    out = []
    for c in rows:
        c.display_name = label(c, me)
        c.peer = peer(c, me)
        c.snippet = (c.last_body or "")[:80]
        if not c.snippet and c.last_attach:
            c.snippet = "[фото]"
        elif c.last_type == "sticker" and c.snippet:
            c.snippet = f"[стикер] {c.snippet}"
        read_at = my_read.get(c.id)
        c.unread = bool(
            c.last_from_id and c.last_from_id != me.id and c.last_at
            and (read_at is None or c.last_at > read_at)
        )
        if unread_only and not c.unread:
            continue
        if sent_only and c.last_from_id != me.id:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def thread(conv: Conversation, before_id=None, limit=50):
    qs = (
        Message.objects.filter(conversation=conv)
        .select_related("social_user", "reply_to", "reply_to__social_user")
    )
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
    orphan = (
        Conversation.objects.filter(community_id__isnull=True, members__social_user=other)
        .annotate(n=Count("members", distinct=True))
        .filter(n=1, messages__social_user=me)
        .order_by("id")
        .first()
    )
    if orphan:
        if not ConversationMember.objects.filter(conversation=orphan, social_user=me).exists():
            ConversationMember.objects.create(conversation=orphan, social_user=me)
        return orphan
    t = now()
    conv = Conversation.objects.create(created_at=t, updated_at=t)
    ConversationMember.objects.bulk_create([
        ConversationMember(conversation=conv, social_user=me),
        ConversationMember(conversation=conv, social_user=other),
    ])
    return conv


def start_thread(me, recipients: list[SocialProfile], subject="") -> Conversation | None:
    """Classic compose: 1 friend → DM; several → group thread with optional subject."""
    ok = []
    for other in recipients:
        if can_dm(me, other) is None:
            ok.append(other)
    if not ok:
        return None
    if len(ok) == 1:
        conv = dm_find_or_create(me, ok[0])
        if subject and not conv.title:
            Conversation.objects.filter(pk=conv.pk).update(title=subject[:160])
            conv.title = subject[:160]
        return conv
    t = now()
    title = (subject or ", ".join(p.name for p in ok[:3]) + ("…" if len(ok) > 3 else ""))[:160]
    conv = Conversation.objects.create(title=title, created_at=t, updated_at=t)
    ConversationMember.objects.bulk_create(
        [ConversationMember(conversation=conv, social_user=me)]
        + [ConversationMember(conversation=conv, social_user=p) for p in ok]
    )
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
    snippet = (m.body or "").strip() or ("[фото]" if m.attachment_path else "")
    body = f"{me.name}: {snippet}"[:255]
    url = f"/messenger?c={conv.id}"
    for pid in peer_ids:
        existing = (
            Notification.objects.filter(social_user_id=pid, type="message", url=url, seen=False)
            .order_by("-id")
            .first()
        )
        if existing:
            existing.body, existing.created_at = body, t
            existing.save(update_fields=["body", "created_at"])
        else:
            Notification.objects.create(
                social_user_id=pid, title="Новое сообщение", body=body,
                seen=False, type="message", url=url, created_at=t,
            )
        cache.delete(f"nav:{pid}")


def _save_attach(upload):
    if not upload:
        return None, None, None
    if getattr(upload, "size", 0) > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return None, None, None
    path = save_image(upload, "messages")
    name = (Path(getattr(upload, "name", "") or "photo").name)[:120]
    mime = (getattr(upload, "content_type", None) or "image/jpeg")[:80]
    return path, name, mime


def post_message(
    me, conv: Conversation, body: str = "", *,
    message_type="text", sticker_id=None, reply_to_id=None, upload=None,
) -> Message:
    body = (body or "").strip()
    path, aname, amime = _save_attach(upload)
    if not body and not path and message_type == "text":
        raise ValueError("empty")
    reply = None
    if reply_to_id:
        reply = Message.objects.filter(pk=int(reply_to_id), conversation=conv).first()
    t = now()
    m = Message.objects.create(
        conversation=conv,
        social_user=me,
        body=(body or ("[фото]" if path else ""))[:4000],
        message_type="photo" if path and message_type == "text" else message_type,
        sticker_id=sticker_id,
        reply_to=reply,
        attachment_path=path,
        attachment_name=aname,
        attachment_mime=amime,
        created_at=t,
        updated_at=t,
    )
    Conversation.objects.filter(pk=conv.pk).update(updated_at=t)
    _revive_dm(conv, me)
    _invalidate_members(conv.id)
    notify_peers(me, conv, m)
    return m


def post_sticker(me, conv: Conversation, sticker: Sticker) -> Message:
    return post_message(me, conv, sticker.phrase or sticker.title, message_type="sticker", sticker_id=sticker.id)


def delete_message(me, message_id) -> int:
    m = get_object_or_404(Message, pk=message_id)
    require_member(me, m.conversation_id)
    if m.social_user_id != me.id:
        raise PermissionError("not yours")
    cid = m.conversation_id
    m.delete()
    last = Message.objects.filter(conversation_id=cid).order_by("-id").first()
    Conversation.objects.filter(pk=cid).update(updated_at=last.created_at if last else now())
    return cid


def ws_payload(m: Message) -> dict:
    reply = m.reply_to
    return {
        "type": "chat.message",
        "id": m.id,
        "body": m.body,
        "name": m.social_user.name,
        "user_id": m.social_user_id,
        "message_type": m.message_type or "text",
        "attachment_url": m.attachment_url or "",
        "reply_to_id": reply.id if reply else None,
        "reply_name": reply.social_user.name if reply else "",
        "reply_body": (reply.body or "")[:80] if reply else "",
    }


def broadcast(m: Message):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(f"chat_{m.conversation_id}", ws_payload(m))


def broadcast_delete(conversation_id, message_id):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(
        f"chat_{conversation_id}",
        {"type": "chat.message", "event": "delete", "id": message_id},
    )


def wants_json(request) -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept or request.headers.get("X-Requested-With") == "XMLHttpRequest"


def json_message(m: Message):
    return JsonResponse(ws_payload(m))


def after_send(m: Message):
    transaction.on_commit(lambda: broadcast(m))
