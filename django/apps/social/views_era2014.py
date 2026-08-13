"""FB 2014 FBVs — Save + Safety Check."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.social import era2014 as e14
from apps.social.models import Post
from apps.social.services import profile_of


def _next(request, default="saves"):
    return request.POST.get("next") or request.GET.get("next") or default


@login_required
@require_GET
def saves_home(request):
    me = profile_of(request.user)
    kind = (request.GET.get("kind") or "").strip()
    rows = e14.list_saves(me, kind=kind, limit=80)
    return render(request, "social/saves.html", {
        "me": me, "items": rows, "kind": kind, "nav": "saves",
    })


@login_required
@require_POST
def save_post_toggle(request, post_id):
    me = profile_of(request.user)
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        messages.error(request, "Запись не найдена.")
        return redirect(_next(request, "feed"))
    _, saved = e14.toggle_save_post(me, post)
    messages.info(request, "Сохранено." if saved else "Убрано из сохранённых.")
    return redirect(_next(request, f"/posts/{post_id}"))


@login_required
@require_POST
def save_add(request):
    me = profile_of(request.user)
    kind = (request.POST.get("kind") or "").strip()
    target_id = request.POST.get("target_id") or request.POST.get("id")
    try:
        target_id = int(target_id) if target_id else None
    except (TypeError, ValueError):
        target_id = None
    row = e14.save_target(
        me, kind=kind, target_id=target_id,
        url=(request.POST.get("url") or "").strip(),
        title=(request.POST.get("title") or "").strip(),
    )
    if row:
        messages.info(request, "Сохранено.")
    else:
        messages.error(request, "Не удалось сохранить.")
    return redirect(_next(request, "saves"))


@login_required
@require_POST
def save_delete(request, pk):
    me = profile_of(request.user)
    e14.unsave(me, pk)
    messages.info(request, "Удалено из сохранённых.")
    return redirect(_next(request, "saves"))


@login_required
@require_GET
def safety_home(request):
    me = profile_of(request.user)
    events = e14.active_safety_events(30)
    if not events:
        e14.ensure_demo_event()
        events = e14.active_safety_events(30)
    return render(request, "social/safety.html", {
        "me": me, "events": events, "nav": "safety",
    })


@login_required
@require_http_methods(["GET", "POST"])
def safety_show(request, pk):
    me = profile_of(request.user)
    event = e14.safety_event_get(pk)
    if not event:
        messages.error(request, "Событие не найдено.")
        return redirect("safety")
    if request.method == "POST":
        status = (request.POST.get("status") or "safe").strip()
        friend_id = request.POST.get("friend_id")
        for_user = None
        if friend_id:
            try:
                from apps.social.models import SocialProfile
                for_user = SocialProfile.objects.filter(pk=int(friend_id)).first()
            except (TypeError, ValueError):
                for_user = None
        row = e14.mark_safe(me, event, status=status, for_user=for_user)
        if row:
            messages.info(
                request,
                "Отмечено: в безопасности." if row.status == "safe" else "Отмечено: не в зоне.",
            )
        else:
            messages.error(request, "Не удалось отметить.")
        return redirect("safety.show", pk=event.id)
    from apps.social import osm
    e14.ensure_safety_geo(event)
    mine = e14.my_checkin(me, event)
    friends_safe = e14.friend_checkins(me, event, 40)
    needing = e14.friends_needing_check(me, event, 20)
    map_ctx = None
    if osm.has_coords(event):
        markers = [{
            "lat": event.lat, "lon": event.lon,
            "title": event.title, "url": event.get_absolute_url(),
        }]
        for row in friends_safe[:12]:
            p = row.social_user
            osm.ensure_profile_geo(p, network=False)
            if osm.has_coords(p):
                markers.append({
                    "lat": p.lat, "lon": p.lon,
                    "title": f"{p.name} — в безопасности",
                    "url": f"/profile/{p.id}",
                })
        map_ctx = osm.map_context(
            event.lat, event.lon,
            zoom=10 if (event.radius_km or 50) >= 30 else 12,
            title=event.city or event.title,
            markers=markers,
        )
    return render(request, "social/safety_event.html", {
        "me": me, "event": event, "mine": mine,
        "friends_safe": friends_safe, "needing": needing,
        "in_area": e14.in_affected_area(me, event),
        "map": map_ctx,
        "nav": "safety",
    })
