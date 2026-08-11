"""Core social FBVs — home, feed, profile, messenger, notifications."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm, PostForm
from apps.social.models import (
    Community, Friendship, Notification, Post, SocialProfile,
)
from apps.social.services import get_profile, now as _now, profile_of


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
    from apps.social.models import Photo
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
    album_photos = list(
        Photo.objects.filter(album__social_user=me).exclude(path="").order_by("-id")[:12]
    ) if me else []
    return render(
        request, "social/feed.html",
        {
            "items": page, "page": page, "me": me,
            "form": PostForm(), "comment_form": CommentForm(),
            "status_form": StatusForm(initial={"headline": me.headline if me else ""}),
            "requests": pending, "birthdays": upcoming_birthdays(me),
            "shared": shared_with(me), "popular_groups": popular,
            "album_photos": album_photos,
        },
    )


@login_not_required
def profile(request, pk):
    from apps.social.forms import StatusForm
    from apps.social.models import Album, Block, Education, Experience, Photo
    from apps.social.services import friend_ids, mini_feed, wall_posts_for
    from apps.social.albums import visible_q
    from apps.social import friendship as fr
    from apps.social import profile_page as pp

    user = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if me and me.id != user.id and fr.is_blocked(me, user):
        return render(request, "social/profile_blocked.html", {"who": user, "me": me}, status=403)

    relation = blocked = None
    can_see = fr.can_see_friends(me, user)
    if me and me.id != user.id:
        relation = Friendship.objects.filter(Q(user=me, friend=user) | Q(user=user, friend=me)).first()
        blocked = Block.objects.filter(blocker=me, blocked=user).exists()
        mutual = fr.mutual_count(me, user)
        mutual_text = fr.mutual_label(mutual) if mutual else ""
    else:
        mutual, mutual_text = 0, ""

    is_own = bool(me and me.id == user.id)
    full = pp.can_view_full(me, user, relation)
    can_wall = pp.can_write_wall(me, user, relation) if full else False
    show_wall = pp.can_view_wall(me, user, relation) if full else False

    education = list(Education.objects.filter(social_user=user)[:10]) if full else []
    experiences = list(Experience.objects.filter(social_user=user)[:10]) if full else []
    networks = pp.networks_for(user, education if full else None)
    friends, friends_are_mutual = pp.friend_tiles(me, user, can_see=can_see, relation=relation)
    communities = (
        Community.objects.filter(memberships__social_user=user).distinct()[:12] if full else []
    )
    photos = pp.recent_photos(user, me, 8) if full else []
    posts = wall_posts_for(user, 20, viewer=me) if show_wall else []
    album_photos = list(
        Photo.objects.filter(album__social_user=me).exclude(path="").order_by("-id")[:12]
    ) if me and can_wall else []
    vis_albums = Album.objects.filter(social_user=user).filter(visible_q(me))
    n_photos = Photo.objects.filter(album__in=vis_albums).count()
    return render(
        request, "social/profile.html",
        {
            "profile": user, "me": me, "is_own": is_own, "limited": not full,
            "friends": friends, "friends_are_mutual": friends_are_mutual,
            "communities": communities, "photos": photos, "posts": posts,
            "relation": relation, "blocked": blocked,
            "mutual": mutual, "mutual_text": mutual_text,
            "education": education, "experiences": experiences, "networks": networks,
            "stats": {
                "friends": len(friend_ids(user)),
                "photos": n_photos,
                "groups": Community.objects.filter(memberships__social_user=user).count() if full else 0,
            },
            "form": PostForm() if can_wall else None,
            "comment_form": CommentForm() if me and show_wall else None,
            "can_wall": can_wall,
            "show_wall": show_wall,
            "can_see_friends": can_see,
            "album_photos": album_photos,
            "mini": mini_feed(user, viewer=me) if full else [],
            "status_form": StatusForm(initial={"headline": user.headline or ""}) if is_own else None,
        },
    )


@login_required
@never_cache
def activity(request):
    me = profile_of(request.user)
    items = list(Notification.objects.filter(social_user=me)[:50]) if me else []
    if me:
        Notification.objects.filter(social_user=me, seen=False).update(seen=True)
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
