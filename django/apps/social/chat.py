"""Classic Facebook inbox — DMs, group threads, attachments, broadcast."""
from __future__ import annotations

from datetime import timedelta
from functools import wraps
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect

from apps.social.friendship import is_blocked
from apps.social.media import save_image
from apps.social.models import Conversation, ConversationMember, Message, Notification, SocialProfile
from apps.social.services import friend_ids, now, profile_of


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


def member_post(view):
    """login + POST + atomic + membership; view(request, me, conv, ...)."""
    @login_required
    @transaction.atomic
    @wraps(view)
    def wrap(request, conversation_id, *args, **kwargs):
        if request.method != "POST":
            return redirect("messenger")
        me = profile_of(request.user)
        if not me:
            return redirect("messenger")
        try:
            conv = require_member(me, conversation_id)
        except Http404:
            messages.error(request, "Диалог недоступен.")
            return redirect("messenger")
        return view(request, me, conv, *args, **kwargs)
    return wrap


def peer(conv: Conversation, me) -> SocialProfile | None:
    peeps = others(conv, me)
    if conv.community_id or len(peeps) != 1:
        return None
    return peeps[0]


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
    t = now()
    ConversationMember.objects.filter(conversation=conv, social_user=me).update(last_read_at=t)
    Message.objects.filter(conversation=conv, read_at__isnull=True).exclude(social_user=me).update(read_at=t)
    Notification.objects.filter(
        social_user=me, type="message", seen=False, url=f"/messenger?c={conv.id}",
    ).update(seen=True)
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


def leave_many(me, conversation_ids: list[int]) -> int:
    """Soft-archive (classic Remove from Inbox) — membership kept, recoverable."""
    t = now()
    n = ConversationMember.objects.filter(
        social_user=me, conversation_id__in=conversation_ids, archived_at__isnull=True,
    ).update(archived_at=t, updated_at=t)
    if n:
        cache.delete(f"nav:{me.id}")
    return n


def leave(me, conv: Conversation):
    leave_many(me, [conv.id])


def restore_many(me, conversation_ids: list[int]) -> int:
    n = ConversationMember.objects.filter(
        social_user=me, conversation_id__in=conversation_ids, archived_at__isnull=False,
    ).update(archived_at=None, updated_at=now())
    if n:
        cache.delete(f"nav:{me.id}")
    return n


def restore(me, conv: Conversation):
    restore_many(me, [conv.id])


def is_archived(me, conv: Conversation) -> bool:
    return ConversationMember.objects.filter(
        conversation=conv, social_user=me, archived_at__isnull=False,
    ).exists()


def mark_unread_many(me, conversation_ids: list[int]) -> int:
    n = 0
    for cid in conversation_ids:
        try:
            mark_unread(me, require_member(me, cid))
            n += 1
        except Http404:
            pass
    return n


def mark_all_read(me) -> int:
    t = now()
    qs = ConversationMember.objects.filter(social_user=me, archived_at__isnull=True)
    ids = list(qs.values_list("conversation_id", flat=True))
    n = qs.update(last_read_at=t)
    if ids:
        Message.objects.filter(conversation_id__in=ids, read_at__isnull=True).exclude(social_user=me).update(read_at=t)
    Notification.objects.filter(social_user=me, type="message", seen=False).update(seen=True)
    cache.delete(f"nav:{me.id}")
    return n


def unread_count(me) -> int:
    """Nav badge — same filter as inbox(unread_only=True)."""
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    my_read = ConversationMember.objects.filter(
        conversation_id=OuterRef("pk"), social_user=me,
    ).values("last_read_at")[:1]
    return (
        Conversation.objects.filter(members__social_user=me, members__archived_at__isnull=True)
        .annotate(
            last_from_id=Subquery(last.values("social_user_id")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            my_read_at=Subquery(my_read),
        )
        .exclude(last_from_id=me.id)
        .filter(last_from_id__isnull=False, last_at__isnull=False)
        .filter(Q(my_read_at__isnull=True) | Q(last_at__gt=F("my_read_at")))
        .distinct()
        .count()
    )


def set_title(me, conv: Conversation, title: str):
    title = (title or "").strip()[:160] or None
    Conversation.objects.filter(pk=conv.pk).update(title=title)
    conv.title = title


def add_members(me, conv: Conversation, profiles: list[SocialProfile]) -> list[SocialProfile]:
    if conv.community_id:
        raise PermissionError("Нельзя менять чат сообщества.")
    added = []
    have = set(
        ConversationMember.objects.filter(conversation=conv).values_list("social_user_id", flat=True)
    )
    for p in profiles:
        if p.id in have or can_dm(me, p) is not None:
            continue
        ConversationMember.objects.create(conversation=conv, social_user=p)
        have.add(p.id)
        added.append(p)
    if added:
        _invalidate_members(conv.id)
        if not conv.title:
            peeps = [m.social_user for m in
                     ConversationMember.objects.filter(conversation=conv).select_related("social_user")
                     if m.social_user_id != me.id]
            title = ", ".join(p.name for p in peeps[:3]) + ("…" if len(peeps) > 3 else "")
            set_title(me, conv, title)
    return added


def _invalidate_members(conv_id):
    for pid in ConversationMember.objects.filter(conversation_id=conv_id).values_list("social_user_id", flat=True):
        cache.delete(f"nav:{pid}")


def _revive_dm(conv: Conversation, me):
    """Re-add dropped DM peers and pull archived members back to inbox."""
    ConversationMember.objects.filter(conversation=conv, archived_at__isnull=False).update(
        archived_at=None, updated_at=now(),
    )
    if conv.community_id:
        return
    past = set(Message.objects.filter(conversation=conv).values_list("social_user_id", flat=True))
    past.add(me.id)
    if len(past) > 2:
        return
    have = set(ConversationMember.objects.filter(conversation=conv).values_list("social_user_id", flat=True))
    for pid in past - have:
        ConversationMember.objects.create(conversation=conv, social_user_id=pid)


def _snippet(c, me) -> str:
    text = (c.last_body or "").strip()
    if not text and c.last_attach:
        text = "[фото]"
    elif c.last_type == "sticker" and text:
        text = f"[стикер] {text}"
    text = text[:80]
    if not text:
        return ""
    names = {m.social_user_id: m.social_user.name for m in c.members.all()}
    if c.last_from_id == me.id:
        who = "Вы"
    else:
        who = names.get(c.last_from_id) or ""
    return f"{who}: {text}" if who else text


def inbox(me, limit=40, offset=0, q="", unread_only=False, sent_only=False, archived_only=False):
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    mine = Message.objects.filter(conversation_id=OuterRef("pk"), social_user=me).order_by("-id")
    my_read_sq = ConversationMember.objects.filter(
        conversation_id=OuterRef("pk"), social_user=me,
    ).values("last_read_at")[:1]
    member_q = Q(members__social_user=me)
    if archived_only:
        member_q &= Q(members__archived_at__isnull=False)
    else:
        member_q &= Q(members__archived_at__isnull=True)
    qs = (
        Conversation.objects.filter(member_q)
        .annotate(
            last_body=Subquery(last.values("body")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            last_type=Subquery(last.values("message_type")[:1]),
            last_from_id=Subquery(last.values("social_user_id")[:1]),
            last_attach=Subquery(last.values("attachment_path")[:1]),
            my_last_body=Subquery(mine.values("body")[:1]),
            my_last_at=Subquery(mine.values("created_at")[:1]),
            my_last_attach=Subquery(mine.values("attachment_path")[:1]),
            my_read_at=Subquery(my_read_sq),
        )
        .prefetch_related(
            Prefetch("members", queryset=ConversationMember.objects.select_related("social_user"))
        )
        .order_by(F("updated_at").desc(nulls_last=True), "-id")
        .distinct()
    )
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(members__social_user__name__icontains=q)
            | Q(messages__body__icontains=q)
        ).distinct()
    if sent_only:
        qs = qs.filter(my_last_at__isnull=False).order_by(F("my_last_at").desc(nulls_last=True), "-id")
    if unread_only:
        qs = (
            qs.exclude(last_from_id=me.id)
            .filter(last_from_id__isnull=False, last_at__isnull=False)
            .filter(Q(my_read_at__isnull=True) | Q(last_at__gt=F("my_read_at")))
        )

    rows = list(qs[offset: offset + limit + 1])
    has_more = len(rows) > limit
    rows = rows[:limit]
    for c in rows:
        c.display_name = label(c, me)
        c.peer = peer(c, me)
        if sent_only:
            text = (c.my_last_body or "").strip() or ("[фото]" if c.my_last_attach else "")
            c.snippet = f"Вы: {text[:80]}" if text else ""
            c.last_at = c.my_last_at or c.last_at
        else:
            c.snippet = _snippet(c, me)
        c.unread = bool(
            c.last_from_id and c.last_from_id != me.id and c.last_at
            and (c.my_read_at is None or c.last_at > c.my_read_at)
        )
    return rows, has_more


def _msg_qs(conv, q=""):
    qs = Message.objects.filter(conversation=conv).select_related("social_user")
    q = (q or "").strip()
    if q:
        qs = qs.filter(body__icontains=q)
    return qs


def thread(conv: Conversation, limit=50, q=""):
    rows = list(_msg_qs(conv, q).order_by("-id")[:limit])
    rows.reverse()
    has_older = bool(rows) and _msg_qs(conv, q).filter(id__lt=rows[0].id).exists()
    return rows, has_older


def older(conv: Conversation, before_id, limit=40, q=""):
    rows = list(_msg_qs(conv, q).filter(id__lt=int(before_id)).order_by("-id")[:limit])
    rows.reverse()
    has_older = bool(rows) and _msg_qs(conv, q).filter(id__lt=rows[0].id).exists()
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
    ok = [other for other in recipients if can_dm(me, other) is None]
    if not ok:
        return None
    if len(ok) == 1:
        conv = dm_find_or_create(me, ok[0])
        if subject and not conv.title:
            set_title(me, conv, subject)
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
    message_type="text", upload=None,
) -> Message:
    body = (body or "").strip()
    path, aname, amime = _save_attach(upload)
    if not body and not path and message_type == "text":
        raise ValueError("empty")
    t = now()
    m = Message.objects.create(
        conversation=conv,
        social_user=me,
        body=(body or ("[фото]" if path else ""))[:4000],
        message_type="photo" if path and message_type == "text" else message_type,
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
    return {
        "type": "chat.message",
        "id": m.id,
        "body": m.body,
        "name": m.social_user.name,
        "user_id": m.social_user_id,
        "message_type": m.message_type or "text",
        "attachment_url": m.attachment_url or "",
        "created_at": m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "",
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
