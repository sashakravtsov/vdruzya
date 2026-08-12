"""Django realtime — SSE badges + inbox thread bump (no separate WS app)."""
from __future__ import annotations

import json
import time

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Max
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

from apps.social import chat as ch
from apps.social import friendship as fr
from apps.social.models import Message, Notification
from apps.social.services import profile_of

INTERVAL = 4
MAX_TICKS = 75  # ~5 min then client reconnects


def _unread(me) -> int:
    key = f"nav:{me.id}"
    cached = cache.get(key)
    if cached is not None:
        return cached[1] if isinstance(cached, (tuple, list)) else int(cached)
    n = ch.unread_count(me)
    cache.set(key, n, 30)
    return n


def snapshot(me, *, conv_id=None) -> dict:
    data = {
        "unread_messages": _unread(me),
        "friend_requests": fr.pending_to(me).count(),
        "pokes": Notification.objects.filter(
            social_user=me, type="poke", seen=False,
        ).count(),
    }
    if conv_id and ch.is_member(me, conv_id):
        data["last_message_id"] = (
            Message.objects.filter(conversation_id=conv_id).aggregate(m=Max("id")).get("m") or 0
        )
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
        .select_related("social_user")
        .order_by("id")[:40]
    )
    if rows and not ch.is_archived(me, conv):
        ch.mark_read(me, conv)
    html = "".join(
        render_to_string(
            "social/_inbox_line.html",
            {"m": m, "me": me, "active": conv, "folder": "inbox"},
            request=request,
        )
        for m in rows
    )
    return JsonResponse({
        "html": html,
        "last_id": rows[-1].id if rows else after,
        "unread_messages": _unread(me),
    })
