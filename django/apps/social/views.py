"""Core social FBVs — home, feed, profile, messenger, notifications."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm
from apps.social.models import Community, Notification
from apps.social.services import get_profile, profile_of


@login_not_required
def home(request):
    if request.user.is_authenticated:
        return redirect("feed")
    return _home_anon(request)


@cache_page(120)
def _home_anon(request):
    return render(request, "social/home.html")


@login_required
@never_cache
def feed(request):
    from apps.social.forms import StatusForm
    from apps.social.services import news_items, shared_with, upcoming_birthdays
    me = profile_of(request.user)
    page = Paginator(news_items(me, 60), 20).get_page(request.GET.get("p"))
    from apps.social import friendship as fr
    pending = fr.annotate_mutuals(me, list(fr.pending_to(me)[:8])) if me else []
    popular = (
        Community.objects.annotate(n=Count("memberships", distinct=True))
        .filter(Q(privacy="public") | Q(privacy=""))
        .order_by("-n", "name")[:6]
    )
    return render(
        request, "social/feed.html",
        {
            "items": page, "page": page, "me": me,
            "comment_form": CommentForm(),
            "status_form": StatusForm(initial={"headline": me.headline if me else ""}),
            "requests": pending, "birthdays": upcoming_birthdays(me),
            "shared": shared_with(me), "popular_groups": popular,
        },
    )


@login_not_required
def profile(request, pk):
    from apps.social import friendship as fr
    from apps.social import profile_page as pp

    user = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if me and me.id != user.id and fr.is_blocked(me, user):
        return render(request, "social/profile_blocked.html", {"who": user, "me": me}, status=403)
    tab = (request.GET.get("tab") or "wall").lower()
    return render(request, "social/profile.html", pp.build_context(user, me, tab=tab))


@login_required
@never_cache
def pokes(request):
    """Classic FB Pokes inbox."""
    me = profile_of(request.user)
    items = list(
        Notification.objects.filter(social_user=me, type="poke").order_by("-id")[:50]
    ) if me else []
    for n in items:
        try:
            n.poker_id = int((n.url or "").rstrip("/").rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            n.poker_id = None
    if me:
        Notification.objects.filter(social_user=me, type="poke", seen=False).update(seen=True)
        cache.delete(f"nav:{me.id}")
    return render(request, "social/pokes.html", {"items": items, "me": me})


@login_required
@never_cache
def activity(request):
    me = profile_of(request.user)
    items = list(Notification.objects.filter(social_user=me).exclude(type="poke")[:50]) if me else []
    if me:
        Notification.objects.filter(social_user=me, seen=False).exclude(type="poke").update(seen=True)
        cache.delete(f"nav:{me.id}")
    return render(request, "social/activity.html", {"items": items, "me": me})


@login_required
@require_POST
def notification_read(request, notification_id):
    me = profile_of(request.user)
    Notification.objects.filter(pk=notification_id, social_user=me).update(seen=True)
    return redirect(request.POST.get("next") or "activity")


@login_required
@require_POST
def notifications_read_all(request):
    me = profile_of(request.user)
    if me:
        Notification.objects.filter(social_user=me, seen=False).update(seen=True)
    return redirect("activity")
