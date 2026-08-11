"""Core social FBVs — home, feed, profile, messenger, notifications."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.http import require_POST

from apps.social.forms import CommentForm, MessageForm, PostForm
from apps.social.models import (
    Community, Conversation, ConversationMember, Friendship, Message, Notification,
    Post, SocialProfile,
)
from apps.social.services import accepted_friends, get_profile, now as _now, profile_of


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
    pending = (
        Friendship.objects.filter(friend=me, status="pending").select_related("user")[:8] if me else []
    )
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
    from apps.social.models import Album, Block, Education, Experience, Photo
    from apps.social.services import friend_ids, mini_feed, wall_posts_for
    from apps.social.albums import visible_q
    from apps.social.views_albums import albums_for_profile
    from apps.social import friendship as fr
    user = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if me and me.id != user.id and fr.is_blocked(me, user):
        return render(request, "social/profile_blocked.html", {"who": user, "me": me}, status=403)
    friends = accepted_friends(user, 6)
    friend_count = len(friend_ids(user))
    communities = Community.objects.filter(memberships__social_user=user).distinct()[:12]
    albums = albums_for_profile(user, me, 4)
    posts = wall_posts_for(user, 20, viewer=me)
    relation = blocked = None
    can_wall = bool(me and me.id == user.id)
    if me and me.id != user.id:
        relation = Friendship.objects.filter(Q(user=me, friend=user) | Q(user=user, friend=me)).first()
        blocked = Block.objects.filter(blocker=me, blocked=user).exists()
        can_wall = bool(relation and relation.status == "accepted")
        mutual = fr.mutual_count(me, user)
    else:
        mutual = 0
    album_photos = list(
        Photo.objects.filter(album__social_user=me).exclude(path="").order_by("-id")[:12]
    ) if me and can_wall else []
    vis_albums = Album.objects.filter(social_user=user).filter(visible_q(me))
    n_photos = Photo.objects.filter(album__in=vis_albums).count()
    return render(
        request, "social/profile.html",
        {
            "profile": user, "me": me, "is_own": bool(me and me.id == user.id),
            "friends": friends, "communities": communities,
            "albums": albums, "posts": posts, "relation": relation, "blocked": blocked,
            "mutual": mutual,
            "education": Education.objects.filter(social_user=user)[:10],
            "experiences": Experience.objects.filter(social_user=user)[:10],
            "stats": {
                "friends": friend_count,
                "photos": n_photos,
                "groups": Community.objects.filter(memberships__social_user=user).count(),
            },
            "form": PostForm() if can_wall else None,
            "comment_form": CommentForm() if me else None,
            "can_wall": can_wall,
            "album_photos": album_photos,
            "mini": mini_feed(user),
        },
    )


@login_required
@never_cache
def messenger(request):
    from apps.social.models import Sticker
    me = profile_of(request.user)
    conv_ids = ConversationMember.objects.filter(social_user=me).values_list("conversation_id", flat=True)
    conversations = Conversation.objects.filter(id__in=conv_ids).order_by("-updated_at", "-id")[:40]
    active_id = request.GET.get("c")
    active = get_object_or_404(Conversation, id=active_id) if active_id else conversations.first()
    messages_qs = Message.objects.filter(conversation=active).select_related("social_user")[:100] if active else []
    if active and me:
        ConversationMember.objects.filter(conversation=active, social_user=me).update(last_read_at=_now())
        cache.delete(f"nav:{me.id}")
    return render(
        request, "social/messenger.html",
        {
            "conversations": conversations, "active": active, "messages": messages_qs,
            "me": me, "form": MessageForm(),
            "stickers": Sticker.objects.filter(is_active=True).order_by("sort_order")[:24],
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


@login_required
def saved(request):
    me = profile_of(request.user)
    posts = (
        Post.objects.filter(saves__social_user=me)
        .select_related("social_user")
        .defer("social_user__looking_for", "social_user__languages")
        .annotate(likes=Count("reactions", distinct=True), n_comments=Count("comments", distinct=True))[:40]
    )
    items = [{"kind": "wall", "at": p.created_at, "post": p, "actor": p.social_user} for p in posts]
    return render(
        request, "social/feed.html",
        {
            "items": items, "me": me, "form": None, "comment_form": CommentForm(),
            "title": "Избранное", "requests": [], "birthdays": [], "shared": [],
            "popular_groups": [], "status_form": None,
        },
    )
