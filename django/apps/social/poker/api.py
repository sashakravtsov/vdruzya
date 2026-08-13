"""JSON API for poker realtime clients (HTTP fallback + initial sync)."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.social.services import profile_of

from . import realtime as rt
from . import service as poker


def _me(request):
    return profile_of(request.user)


@login_required
@require_GET
def table_state(request, game_id: int):
    me = _me(request)
    if not me:
        return JsonResponse({"ok": False, "error": "auth"}, status=403)
    game = poker.game_for(me, game_id)
    if not game:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)
    data = rt.serialize_table(game, me)
    data["event"] = "sync"
    return JsonResponse(data)


@login_required
@require_GET
def room_state(request, room_id: int):
    me = _me(request)
    if not me:
        return JsonResponse({"ok": False, "error": "auth"}, status=403)
    room = poker.room_for(me, room_id)
    if not room or room.status == "closed":
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)
    data = rt.serialize_room(room, me)
    data["event"] = "sync"
    return JsonResponse(data)


@login_required
@require_POST
def table_act(request, game_id: int):
    me = _me(request)
    if not me:
        return JsonResponse({"ok": False, "error": "auth"}, status=403)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        body = request.POST
    play = (body.get("play") or "").strip()
    try:
        raise_to = int(body.get("raise_to") or 0)
    except (TypeError, ValueError):
        raise_to = 0
    try:
        game = poker.act(me, game_id, play, raise_to=raise_to)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "error": "fail"}, status=500)
    rt.notify_game(game, event="acted")
    data = rt.serialize_table(game, me)
    data["event"] = "acted"
    return JsonResponse(data)
