"""Core social FBVs — home, feed, profile, pokes, notifications."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page, never_cache

from apps.social.forms import CommentForm
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
    from apps.social import browse_filters as bf
    from apps.social import classic_extra as cx

    me = profile_of(request.user)
    filt = bf.feed_filter(request.GET.get("filter"))
    flist = cx.owned_list(me, request.GET.get("list"))
    actor_ids = cx.list_member_ids(flist) if flist else None
    items = bf.apply_feed(
        news_items(me, 120), filt, actor_ids=actor_ids, me=me,
    )
    page = Paginator(items, 20).get_page(request.GET.get("p"))
    return render(
        request, "social/feed.html",
        {
            "items": page, "page": page, "me": me,
            "comment_form": CommentForm(),
            "nav": "feed",
            "feed_filter": filt,
            "feed_tabs": bf.FEED_TABS,
            "friend_lists": cx.lists_for(me),
            "active_list": flist,
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
    wall_filter = (request.GET.get("filter") or "all").lower()
    if request.GET.get("y") and str(request.GET.get("y")).isdigit():
        user._timeline_year = int(request.GET.get("y"))
    return render(request, "social/profile.html", pp.build_context(
        user, me, tab=tab, photos_view=request.GET.get("view") or "albums",
        wall_filter=wall_filter,
    ))


@login_required
def wall_to_wall(request, pk):
    """FB 2005 Wall-to-Wall between viewer and profile."""
    from apps.social import friendship as fr
    from apps.social.compose_ui import editor_context
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
        "form": PostForm(simple=True) if can_write else None,
        "nav": "friends",
        **editor_context(stickers=False),
    })


@login_required
def see_friendship(request, pk):
    """FB 2009 «Смотреть дружбу» — mutuals, since, shared groups/photos, W2W link."""
    from apps.social import friendship as fr
    from apps.social.services import wall_to_wall as w2w

    other = get_profile(pk)
    me = profile_of(request.user)
    if not me or me.id == other.id:
        return redirect(other)
    if fr.is_blocked(me, other):
        return render(request, "social/profile_blocked.html", {"who": other, "me": me}, status=403)
    data = fr.friendship_page(me, other)
    wall_preview = []
    if data["are_friends"]:
        from apps.social.likes import attach_likes
        from apps.social.shares import attach_share_flags
        wall_preview = w2w(me, other, limit=5, viewer=me)
        attach_likes(wall_preview, me)
        attach_share_flags(wall_preview, me)
    return render(request, "social/friendship.html", {
        "me": me, "other": other,
        "since": data["since"],
        "are_friends": data["are_friends"],
        "mutual": data["mutual"],
        "mutual_count": data["mutual_count"],
        "mutual_label": fr.mutual_label(data["mutual_count"]) if data["mutual_count"] else "",
        "groups": data["groups"],
        "photos": data["photos"],
        "wall_preview": wall_preview,
        "nav": "friends",
    })


@login_required
@never_cache
def pokes(request):
    """Classic FB Pokes inbox."""
    me = profile_of(request.user)
    from apps.social import notify
    items = notify.for_user(me, type="poke", limit=50)
    notify.attach_poker_ids(items)
    notify.mark_seen(me, type="poke")
    return render(request, "social/pokes.html", {"items": items, "me": me, "nav": "pokes"})


@login_required
@never_cache
def notifications(request):
    """Classic FB Notifications — all types (not poke-only)."""
    me = profile_of(request.user)
    from apps.social import notify
    items = notify.for_user(me, limit=60)
    notify.attach_actors(items)
    for n in items:
        n.type_label = notify.type_label(n)
    notify.mark_seen(me)
    return render(
        request, "social/notifications.html",
        {"items": items, "me": me, "nav": "notifications"},
    )
