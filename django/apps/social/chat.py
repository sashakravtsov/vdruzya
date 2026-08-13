"""Classic Facebook Inbox — 1:1 HTTP messages (FB 2006)."""
from __future__ import annotations

from datetime import timedelta
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect

from apps.social.friendship import is_blocked
from apps.social.media import (
    VIDEO_MAX_BYTES,
    parse_duration_ms, parse_waveform_peaks,
    save_audio, save_video, serialize_waveform_peaks, voice_body,
    waveform_from_bytes,
)
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
            return redirect("inbox")
        me = profile_of(request.user)
        if not me:
            return redirect("inbox")
        try:
            conv = require_member(me, conversation_id)
        except Http404:
            messages.error(request, "Диалог недоступен.")
            return redirect("inbox")
        return view(request, me, conv, *args, **kwargs)
    return wrap


def peer(conv: Conversation, me) -> SocialProfile | None:
    """1:1 peer only — community/group threads are not classic Inbox."""
    if getattr(conv, "community_id", None):
        return None
    peeps = others(conv, me)
    return peeps[0] if len(peeps) == 1 else None


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
        social_user=me, type="message", seen=False, url=f"/inbox?c={conv.id}",
    ).update(seen=True)
    cache.delete(f"nav:{me.id}")


def mark_unread(me, conv: Conversation):
    """Classic «оставить непрочитанным» — bump last_read before last peer message."""
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
    """Soft-archive several threads (classic Remove from Inbox)."""
    ids = [int(x) for x in conversation_ids if str(x).isdigit() or isinstance(x, int)]
    if not ids:
        return 0
    t = now()
    n = ConversationMember.objects.filter(
        social_user=me, conversation_id__in=ids, archived_at__isnull=True,
    ).update(archived_at=t, updated_at=t)
    if n:
        cache.delete(f"nav:{me.id}")
    return n


def leave(me, conv: Conversation):
    """Soft-archive (classic Remove from Inbox) — membership kept."""
    leave_many(me, [conv.id])


def restore_many(me, conversation_ids: list[int]) -> int:
    ids = [int(x) for x in conversation_ids if str(x).isdigit() or isinstance(x, int)]
    if not ids:
        return 0
    n = ConversationMember.objects.filter(
        social_user=me, conversation_id__in=ids, archived_at__isnull=False,
    ).update(archived_at=None, updated_at=now())
    if n:
        cache.delete(f"nav:{me.id}")
    return n


def unarchive(me, conv: Conversation) -> bool:
    """Restore a soft-archived conversation to the Inbox list."""
    return bool(restore_many(me, [conv.id]))


def purge_many(me, conversation_ids: list[int]) -> int:
    """Hard-remove from mailbox — membership gone until revive on DM reply."""
    ids = [int(x) for x in conversation_ids if str(x).isdigit() or isinstance(x, int)]
    if not ids:
        return 0
    n = ConversationMember.objects.filter(
        social_user=me, conversation_id__in=ids,
    ).delete()[0]
    if n:
        cache.delete(f"nav:{me.id}")
    return n


def report_spam(me, conv: Conversation) -> SocialProfile | None:
    """Classic Report as Spam: archive thread; return DM peer for optional block."""
    p = peer(conv, me)
    leave(me, conv)
    return p


def is_archived(me, conv: Conversation) -> bool:
    return ConversationMember.objects.filter(
        conversation=conv, social_user=me, archived_at__isnull=False,
    ).exists()


def mute(me, conv: Conversation) -> bool:
    """Silence message notifications for this thread (membership kept)."""
    t = now()
    n = ConversationMember.objects.filter(
        social_user=me, conversation=conv, muted_at__isnull=True,
    ).update(muted_at=t, updated_at=t)
    return bool(n)


def unmute(me, conv: Conversation) -> bool:
    t = now()
    n = ConversationMember.objects.filter(
        social_user=me, conversation=conv, muted_at__isnull=False,
    ).update(muted_at=None, updated_at=t)
    return bool(n)


def is_muted(me, conv: Conversation) -> bool:
    return ConversationMember.objects.filter(
        conversation=conv, social_user=me, muted_at__isnull=False,
    ).exists()


def peer_read_at(me, conv: Conversation):
    """When the 1:1 peer last opened the thread (for read receipts)."""
    row = (
        ConversationMember.objects.filter(conversation=conv)
        .exclude(social_user=me)
        .order_by("id")
        .values_list("last_read_at", flat=True)
        .first()
    )
    return row


def mark_all_read(me) -> int:
    """Mark every non-archived inbox thread as read (classic Message Center)."""
    t = now()
    conv_ids = list(
        ConversationMember.objects.filter(
            social_user=me, archived_at__isnull=True,
        ).values_list("conversation_id", flat=True)
    )
    if not conv_ids:
        Notification.objects.filter(social_user=me, type="message", seen=False).update(seen=True)
        cache.delete(f"nav:{me.id}")
        return 0
    ConversationMember.objects.filter(
        social_user=me, conversation_id__in=conv_ids,
    ).update(last_read_at=t, updated_at=t)
    Message.objects.filter(
        conversation_id__in=conv_ids, read_at__isnull=True,
    ).exclude(social_user=me).update(read_at=t)
    Notification.objects.filter(social_user=me, type="message", seen=False).update(seen=True)
    cache.delete(f"nav:{me.id}")
    return len(conv_ids)


def unread_count(me) -> int:
    """Nav badge — same filter as inbox(unread_only=True)."""
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    my_read = ConversationMember.objects.filter(
        conversation_id=OuterRef("pk"), social_user=me,
    ).values("last_read_at")[:1]
    return (
        Conversation.objects.filter(
            community_id__isnull=True,
            members__social_user=me, members__archived_at__isnull=True,
        )
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
        lt = (getattr(c, "last_type", None) or "")
        if lt == "voice":
            text = voice_body(getattr(c, "last_duration", None))
        else:
            text = "[видео]" if lt == "video" else "[фото]"
    text = text[:80]
    if not text:
        return ""
    names = {m.social_user_id: m.social_user.name for m in c.members.all()}
    if c.last_from_id == me.id:
        who = "Вы"
    else:
        who = names.get(c.last_from_id) or ""
    return f"{who}: {text}" if who else text


def _inbox_qs(me, *, archived=False):
    last = Message.objects.filter(conversation_id=OuterRef("pk")).order_by("-id")
    mine = Message.objects.filter(conversation_id=OuterRef("pk"), social_user=me).order_by("-id")
    my_read_sq = ConversationMember.objects.filter(
        conversation_id=OuterRef("pk"), social_user=me,
    ).values("last_read_at")[:1]
    mem = {"members__social_user": me}
    if archived:
        mem["members__archived_at__isnull"] = False
    else:
        mem["members__archived_at__isnull"] = True
    return (
        Conversation.objects.filter(community_id__isnull=True, **mem)
        .annotate(
            last_body=Subquery(last.values("body")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            last_type=Subquery(last.values("message_type")[:1]),
            last_duration=Subquery(last.values("duration_ms")[:1]),
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


def _filter_inbox(qs, me, *, q="", unread_only=False, sent_only=False):
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
    return qs


def _decorate_inbox(rows, me, *, sent_only=False):
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
    return rows


def inbox(me, limit=40, offset=0, q="", unread_only=False, sent_only=False, archived=False):
    qs = _filter_inbox(
        _inbox_qs(me, archived=archived), me,
        q=q, unread_only=unread_only and not archived, sent_only=sent_only and not archived,
    )
    rows = list(qs[offset: offset + limit + 1])
    has_more = len(rows) > limit
    return _decorate_inbox(rows[:limit], me, sent_only=sent_only and not archived), has_more


def _msg_qs(conv, q=""):
    qs = (
        Message.objects.filter(conversation=conv)
        .select_related("social_user", "reply_to", "reply_to__social_user")
    )
    q = (q or "").strip()
    if q:
        qs = qs.filter(body__icontains=q)
    return qs


def attach_message_stickers(rows):
    ids = {m.sticker_id for m in rows if getattr(m, "sticker_id", None)}
    if not ids:
        for m in rows:
            m.sticker = None
        return rows
    from apps.social.models import Sticker
    by_id = Sticker.objects.in_bulk(ids)
    for m in rows:
        m.sticker = by_id.get(m.sticker_id) if m.sticker_id else None
    return rows


def thread(conv: Conversation, limit=50, q="", *, all_messages=False):
    qs = _msg_qs(conv, q).order_by("-id")
    if all_messages:
        rows = list(qs)
        rows.reverse()
    else:
        rows = list(qs[:limit])
        rows.reverse()
        has_older = bool(rows) and _msg_qs(conv, q).filter(id__lt=rows[0].id).exists()
        attach_message_stickers(rows)
        return rows, has_older
    attach_message_stickers(rows)
    return rows, False


def older(conv: Conversation, before_id, limit=40, q=""):
    """Paginated earlier messages (classic «более ранние» without ?all=1)."""
    try:
        before = int(before_id)
    except (TypeError, ValueError):
        return [], False
    rows = list(_msg_qs(conv, q).filter(id__lt=before).order_by("-id")[:limit])
    rows.reverse()
    has_older = bool(rows) and _msg_qs(conv, q).filter(id__lt=rows[0].id).exists()
    attach_message_stickers(rows)
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
    """1:1 only — classic Inbox had no multi-recipient group chat."""
    ok = [other for other in recipients if can_dm(me, other) is None]
    if len(ok) != 1:
        return None
    conv = dm_find_or_create(me, ok[0])
    if subject and not conv.title:
        set_title(me, conv, subject)
    return conv


def notify_peers(me, conv: Conversation, m: Message):
    peers = list(
        ConversationMember.objects.filter(conversation=conv)
        .exclude(social_user=me)
        .values_list("social_user_id", "muted_at")
    )
    if not peers:
        return
    t = now()
    mt = (m.message_type or "")
    snippet = (m.body or "").strip() or (
        voice_body(m.duration_ms) if mt == "voice"
        else "[видео]" if mt == "video" or (m.attachment_mime or "").startswith("video/")
        else ("[фото]" if m.attachment_path else "")
    )
    body = f"{me.name}: {snippet}"[:255]
    url = f"/inbox?c={conv.id}"
    for pid, muted_at in peers:
        cache.delete(f"nav:{pid}")
        if muted_at:
            continue
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


_VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}


def _is_video_upload(upload) -> bool:
    name = (getattr(upload, "name", "") or "").lower()
    ctype = (getattr(upload, "content_type", "") or "").lower()
    return Path(name).suffix in _VIDEO_EXT or ctype.startswith("video/")


def _save_attach(upload, *, force_voice=False):
    """Save photo / video / voice. Voice → (path, name, mime, kind, raw_bytes)."""
    if not upload:
        return None, None, None, None, None
    size = getattr(upload, "size", 0) or 0
    ctype = (getattr(upload, "content_type", "") or "").lower()
    as_voice = force_voice or ctype.startswith("audio/") or ctype == "application/ogg"
    if as_voice:
        # save_audio enforces size/empty; surface ValueError to the view
        path, raw = save_audio(upload, "messages")
        name = (Path(getattr(upload, "name", "") or "voice.webm").name)[:120]
        mime = (getattr(upload, "content_type", None) or "audio/webm")[:80]
        return path, name, mime, "voice", raw
    if _is_video_upload(upload):
        if size > VIDEO_MAX_BYTES:
            return None, None, None, None, None
        try:
            path, _poster = save_video(upload, "messages")
        except Exception:
            return None, None, None, None, None
        name = (Path(getattr(upload, "name", "") or "video.mp4").name)[:120]
        mime = (getattr(upload, "content_type", None) or "video/mp4")[:80]
        return path, name, mime, "video", None
    if size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return None, None, None, None, None
    from apps.social.media import try_save_image
    path = try_save_image(upload, "messages")
    if not path:
        return None, None, None, None, None
    name = (Path(getattr(upload, "name", "") or "photo").name)[:120]
    mime = (getattr(upload, "content_type", None) or "image/jpeg")[:80]
    return path, name, mime, "photo", None


def _sticker_id(sticker_id):
    if not sticker_id:
        return None
    try:
        sid = int(sticker_id)
    except (TypeError, ValueError):
        return None
    from apps.social.models import Sticker
    return sid if Sticker.objects.filter(pk=sid, is_active=True).exists() else None


def _message_payload(body, path, akind, sid, message_type, *, duration_ms=None):
    body = (body or "").strip()
    if not body and not path and not sid and message_type == "text":
        raise ValueError("empty")
    if sid and not body:
        body = "[стикер]"
    if path and message_type == "text":
        message_type = akind or "photo"
    elif sid:
        message_type = "sticker"
    if not body and path:
        if message_type == "voice":
            body = voice_body(duration_ms)
        elif message_type == "video":
            body = "[видео]"
        else:
            body = "[фото]"
    return body[:4000], message_type


def _resolve_voice_meta(*, client_wave=None, client_ms=None, raw=None, copy_from=None):
    wave = serialize_waveform_peaks(parse_waveform_peaks(client_wave))
    ms = parse_duration_ms(client_ms)
    if copy_from and (copy_from.waveform or copy_from.duration_ms):
        wave = wave or copy_from.waveform
        ms = ms or copy_from.duration_ms
    if (not wave or not ms) and raw:
        fw, fms = waveform_from_bytes(raw)
        wave = wave or fw
        ms = ms or fms
    return wave, ms


def post_message(
    me, conv: Conversation, body: str = "", *,
    message_type="text", upload=None, reply_to_id=None, sticker_id=None,
    voice=False, copy_from: Message | None = None,
    waveform=None, duration_ms=None,
) -> Message:
    path, aname, amime, akind, raw = _save_attach(upload, force_voice=bool(voice))
    if copy_from and copy_from.attachment_path and not path:
        path = copy_from.attachment_path
        aname = copy_from.attachment_name
        amime = copy_from.attachment_mime
        mt = (copy_from.message_type or "")
        if mt in ("voice", "video", "photo"):
            akind = mt
        elif copy_from.attachment_is_audio:
            akind = "voice"
        elif copy_from.attachment_is_video:
            akind = "video"
        else:
            akind = "photo"
    sid = _sticker_id(sticker_id or (copy_from.sticker_id if copy_from else None))
    if voice and akind == "voice":
        message_type = "voice"
    wave = ms = None
    if akind == "voice" or message_type == "voice":
        message_type = "voice"
        wave, ms = _resolve_voice_meta(
            client_wave=waveform, client_ms=duration_ms, raw=raw, copy_from=copy_from,
        )
    body, message_type = _message_payload(
        body, path, akind, sid, message_type, duration_ms=ms,
    )
    reply = (
        Message.objects.filter(pk=reply_to_id, conversation=conv).first()
        if reply_to_id else None
    )
    t = now()
    m = Message.objects.create(
        conversation=conv, social_user=me, body=body,
        message_type=message_type, sticker_id=sid, reply_to=reply,
        attachment_path=path, attachment_name=aname, attachment_mime=amime,
        waveform=wave if message_type == "voice" else None,
        duration_ms=ms if message_type == "voice" else None,
        created_at=t, updated_at=t,
    )
    Conversation.objects.filter(pk=conv.pk).update(updated_at=t)
    _revive_dm(conv, me)
    _invalidate_members(conv.id)
    notify_peers(me, conv, m)
    return m


def forward_message(me, message_id, other: SocialProfile) -> tuple[Message, Conversation]:
    src = get_object_or_404(Message.objects.select_related("social_user"), pk=message_id)
    require_member(me, src.conversation_id)
    err = can_dm(me, other)
    if err:
        raise PermissionError(err)
    conv = dm_find_or_create(me, other)
    quote = (src.body or "").strip() or (
        voice_body(src.duration_ms) if src.attachment_is_audio
        else "[видео]" if src.attachment_is_video
        else ("[фото]" if src.attachment_path else ("[стикер]" if src.sticker_id else ""))
    )
    body = f"Переслано от {src.social_user.name}:\n{quote}"[:4000]
    m = post_message(
        me, conv, body,
        copy_from=src if (src.attachment_path or src.sticker_id) else None,
        sticker_id=src.sticker_id if src.sticker_id and not src.attachment_path else None,
    )
    return m, conv


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
