"""Events, DM start, groups join/leave, push."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social.models import (
    Community,
    CommunityMember,
    Conversation,
    ConversationMember,
    Event,
    EventAttendee,
    PushSubscription,
    SocialProfile,
)
from apps.social.services import now as _now, profile_of


@login_required
def events(request):
    me = profile_of(request.user)
    if request.method == "POST" and me:
        title = (request.POST.get("title") or "").strip()
        place = (request.POST.get("place") or "").strip() or "—"
        starts = request.POST.get("starts_at")
        if title and starts:
            Event.objects.create(title=title, place=place, starts_at=starts)
            messages.success(request, "Событие добавлено.")
            return redirect("events")
    items = Event.objects.annotate(going=Count("attendees")).order_by("starts_at")[:50]
    my = set(EventAttendee.objects.filter(social_user=me).values_list("event_id", flat=True)) if me else set()
    return render(request, "social/events.html", {"events": items, "my": my, "me": me})


@login_required
@require_POST
def event_rsvp(request, event_id):
    me = profile_of(request.user)
    event = get_object_or_404(Event, pk=event_id)
    row = EventAttendee.objects.filter(event=event, social_user=me).first()
    if row:
        row.delete()
    elif me:
        EventAttendee.objects.create(event=event, social_user=me, status="going", created_at=_now())
    return redirect(request.POST.get("next") or "events")


@login_required
@require_POST
def group_join(request, pk):
    from apps.social.models import CommunityJoinRequest
    from django.core.cache import cache
    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    if not me:
        return redirect("groups.show", pk=pk)
    if CommunityMember.objects.filter(community=group, social_user=me).exists():
        return redirect("groups.show", pk=pk)
    if group.join_mode == "open" and group.privacy != "closed":
        CommunityMember.objects.create(community=group, social_user=me, role="member", created_at=_now())
        messages.success(request, f"Вы в группе «{group.name}».")
        cache.delete(f"news:{me.id}:60")
    else:
        CommunityJoinRequest.objects.get_or_create(
            community=group, social_user=me,
            defaults={"status": "pending", "created_at": _now()},
        )
        messages.info(request, "Заявка на вступление отправлена.")
    return redirect("groups.show", pk=pk)


@login_required
@require_POST
def group_leave(request, pk):
    from django.core.cache import cache
    me = profile_of(request.user)
    group = get_object_or_404(Community, pk=pk)
    row = CommunityMember.objects.filter(community=group, social_user=me).first()
    if not row:
        return redirect("groups.show", pk=pk)
    if row.role == "admin" and not CommunityMember.objects.filter(community=group, role="admin").exclude(pk=row.pk).exists():
        messages.error(request, "Нельзя выйти: вы единственный администратор.")
        return redirect("groups.show", pk=pk)
    row.delete()
    cache.delete(f"news:{me.id}:60")
    messages.success(request, f"Вы вышли из «{group.name}».")
    return redirect("groups")


@login_required
@require_POST
@transaction.atomic
def messenger_start(request, pk):
    me = profile_of(request.user)
    other = get_object_or_404(SocialProfile, pk=pk)
    if not me or me.id == other.id:
        return redirect("messenger")
    mine = set(ConversationMember.objects.filter(social_user=me).values_list("conversation_id", flat=True))
    shared = mine & set(ConversationMember.objects.filter(social_user=other).values_list("conversation_id", flat=True))
    if shared:
        cid = min(shared)
    else:
        now = _now()
        conv = Conversation.objects.create(created_at=now, updated_at=now)
        ConversationMember.objects.bulk_create([
            ConversationMember(conversation=conv, social_user=me),
            ConversationMember(conversation=conv, social_user=other),
        ])
        cid = conv.id
    return redirect(f"/messenger?c={cid}")


@login_required
@require_POST
def push_store(request):
    me = profile_of(request.user)
    try:
        data = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False}, status=400)
    keys = data.get("keys") or {}
    if not me or not data.get("endpoint"):
        return JsonResponse({"ok": False}, status=400)
    PushSubscription.objects.update_or_create(
        social_user=me, endpoint=data["endpoint"],
        defaults={
            "public_key": keys.get("p256dh", ""),
            "auth_token": keys.get("auth", ""),
            "content_encoding": data.get("contentEncoding", "aes128gcm"),
            "created_at": _now(),
        },
    )
    return JsonResponse({"ok": True})
