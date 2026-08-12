"""Core social FBVs — home, feed, profile, pokes."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page, never_cache

from apps.social.forms import CommentForm
from apps.social.models import Notification
from apps.social.services import feed_rail, get_profile, news_items, profile_of


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
    me = profile_of(request.user)
    page = Paginator(news_items(me, 60), 20).get_page(request.GET.get("p"))
    return render(
        request, "social/feed.html",
        {
            "items": page, "page": page, "me": me,
            "comment_form": CommentForm(),
            "nav": "feed",
            **feed_rail(me),
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
def wall_to_wall(request, pk):
    """FB 2005 Wall-to-Wall between viewer and profile."""
    from apps.social import friendship as fr
    from apps.social.forms import CommentForm, PostForm
    from apps.social.services import friend_ids, wall_to_wall as w2w

    other = get_profile(pk)
    me = profile_of(request.user)
    if not me or me.id == other.id:
        return redirect(other)
    if fr.is_blocked(me, other):
        return render(request, "social/profile_blocked.html", {"who": other, "me": me}, status=403)
    posts = w2w(me, other, limit=40, viewer=me)
    can_write = other.id in friend_ids(me)
    return render(request, "social/wall_to_wall.html", {
        "me": me, "other": other, "posts": posts,
        "comment_form": CommentForm(),
        "form": PostForm() if can_write else None,
        "nav": "friends",
    })


@login_required
@never_cache
def pokes(request):
    """Classic FB Pokes inbox."""
    me = profile_of(request.user)
    from apps.social.notify import attach_poker_ids
    items = list(
        Notification.objects.filter(social_user=me, type="poke").order_by("-id")[:50]
    ) if me else []
    attach_poker_ids(items)
    if me:
        Notification.objects.filter(social_user=me, type="poke", seen=False).update(seen=True)
        cache.delete(f"nav:{me.id}")
    return render(request, "social/pokes.html", {"items": items, "me": me})
