"""Django realtime — SSE badges + inbox thread bump (no separate WS app)."""
from __future__ import annotations

import json
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Max
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from apps.social import chat as ch
from apps.social import friendship as fr
from apps.social.models import ConversationMember, Message, Notification
from apps.social.services import profile_of

INTERVAL = 4
MAX_TICKS = 75  # ~5 min then client reconnects
TYPING_TTL = 6
TYPING_STATES = frozenset({"typing", "voice"})


def _unread(me) -> int:
    key = f"nav:{me.id}"
    cached = cache.get(key)
    if cached is not None:
        return cached[1] if isinstance(cached, (tuple, list)) else int(cached)
    n = ch.unread_count(me)
    cache.set(key, n, 30)
    return n


def _typing_key(conv_id: int, user_id: int) -> str:
    return f"typing:{conv_id}:{user_id}"


def set_typing(me, conv_id: int, state: str = "typing") -> bool:
    """Mark presence for classic Inbox (cache TTL; SSE picks it up)."""
    if not me or not conv_id or not ch.is_member(me, conv_id):
        return False
    state = (state or "typing").strip().lower()
    if state not in TYPING_STATES:
        state = "typing"
    cache.set(
        _typing_key(conv_id, me.id),
        {"id": me.id, "name": me.name or "Кто-то", "state": state},
        TYPING_TTL,
    )
    return True


def typing_for(me, conv_id: int) -> list[dict]:
    if not me or not conv_id or not ch.is_member(me, conv_id):
        return []
    peer_ids = list(
        ConversationMember.objects.filter(conversation_id=conv_id)
        .exclude(social_user_id=me.id)
        .values_list("social_user_id", flat=True)[:20]
    )
    out = []
    for pid in peer_ids:
        row = cache.get(_typing_key(conv_id, pid))
        if isinstance(row, dict) and row.get("name"):
            out.append({
                "id": int(row.get("id") or pid),
                "name": str(row["name"])[:80],
                "state": row.get("state") if row.get("state") in TYPING_STATES else "typing",
            })
    return out


def _peer_read_iso(me, conv_id: int) -> str | None:
    try:
        conv = ch.require_member(me, conv_id)
    except Http404:
        return None
    ts = ch.peer_read_at(me, conv)
    if not ts:
        return None
    try:
        return ts.isoformat()
    except Exception:
        return str(ts)


def snapshot(me, *, conv_id=None) -> dict:
    from apps.social import notify

    data = {
        "unread_messages": _unread(me),
        "friend_requests": fr.pending_to(me).count(),
        "pokes": Notification.objects.filter(
            social_user=me, type="poke", seen=False,
        ).count(),
        "notifications": notify.unread_count(me),
    }
    if conv_id and ch.is_member(me, conv_id):
        data["last_message_id"] = (
            Message.objects.filter(conversation_id=conv_id).aggregate(m=Max("id")).get("m") or 0
        )
        data["typing"] = typing_for(me, conv_id)
        data["peer_read_at"] = _peer_read_iso(me, conv_id)
    return data


def _sse(me, conv_id=None):
    last = None
    for _ in range(MAX_TICKS):
        snap = snapshot(me, conv_id=conv_id)
        if snap != last:
            yield f"data: {json.dumps(snap, separators=(',', ':'))}\n\n"
            last = snap
        else:
            yield ": ping\n\n"
        time.sleep(INTERVAL)


@login_required
@require_GET
def stream(request):
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    conv_id = int(request.GET["c"]) if (request.GET.get("c") or "").isdigit() else None
    if request.GET.get("once") == "1":
        body = f"data: {json.dumps(snapshot(me, conv_id=conv_id), separators=(',', ':'))}\n\n"

        def one():
            yield body

        gen = one()
    else:
        gen = _sse(me, conv_id)
    resp = StreamingHttpResponse(gen, content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache, no-transform"
    resp["X-Accel-Buffering"] = "no"
    return resp


@login_required
@require_POST
def inbox_typing(request, conversation_id):
    """Ping «печатает» / «записывает голосовое» for SSE peers (no WS messenger)."""
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    state = (request.POST.get("state") or "typing").strip().lower()
    if not set_typing(me, conversation_id, state):
        return JsonResponse({"error": "forbidden"}, status=403)
    return JsonResponse({"ok": True, "state": state if state in TYPING_STATES else "typing"})


@login_required
@require_GET
def inbox_since(request, conversation_id):
    """HTML fragment of new classic inbox lines after `after` id."""
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    try:
        conv = ch.require_member(me, conversation_id)
    except Http404:
        return JsonResponse({"error": "forbidden"}, status=403)
    try:
        after = int(request.GET.get("after") or 0)
    except (TypeError, ValueError):
        after = 0
    rows = list(
        Message.objects.filter(conversation=conv, id__gt=after)
        .select_related("social_user", "reply_to", "reply_to__social_user")
        .order_by("id")[:40]
    )
    ch.attach_message_stickers(rows)
    if rows and not ch.is_archived(me, conv):
        ch.mark_read(me, conv)
    peer_ts = ch.peer_read_at(me, conv)
    from apps.social.services import accepted_friends as friends_of
    friends = list(friends_of(me, limit=200))
    html = "".join(
        render_to_string(
            "social/_inbox_line.html",
            {"m": m, "me": me, "active": conv, "folder": "inbox", "friends": friends},
            request=request,
        )
        for m in rows
    )
    return JsonResponse({
        "html": html,
        "last_id": rows[-1].id if rows else after,
        "unread_messages": _unread(me),
        "typing": typing_for(me, conversation_id),
        "peer_read_at": peer_ts.isoformat() if peer_ts else None,
    })


@login_required
@require_GET
def inbox_older(request, conversation_id):
    """HTML fragment of earlier classic inbox lines before `before` id."""
    me = profile_of(request.user)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    try:
        conv = ch.require_member(me, conversation_id)
    except Http404:
        return JsonResponse({"error": "forbidden"}, status=403)
    tq = (request.GET.get("tq") or "").strip()
    rows, has_older = ch.older(conv, request.GET.get("before"), limit=40, q=tq)
    from apps.social.services import accepted_friends as friends_of
    friends = list(friends_of(me, limit=200))
    html = "".join(
        render_to_string(
            "social/_inbox_line.html",
            {"m": m, "me": me, "active": conv, "folder": "inbox", "friends": friends, "tq": tq},
            request=request,
        )
        for m in rows
    )
    try:
        before = int(request.GET.get("before") or 0)
    except (TypeError, ValueError):
        before = 0
    return JsonResponse({
        "html": html,
        "first_id": rows[0].id if rows else before,
        "has_older": has_older,
    })
