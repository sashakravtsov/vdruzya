from datetime import datetime, timedelta

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.social.models import (
    Block, Comment, Community, CommunityMember, CommunityPost, Friendship, Post,
    SocialProfile,
)


def now():
    t = timezone.now()
    return timezone.make_naive(t) if timezone.is_aware(t) else t


def profile_of(user) -> SocialProfile | None:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "profile", None) or SocialProfile.objects.filter(user_id=user.id).first()


def accepted_friends(profile: SocialProfile, limit=6):
    """Owner's friends by name — subquery, no full id set in Python."""
    pid = profile.id
    out = Friendship.objects.filter(status="accepted", user_id=pid).values("friend_id")
    inn = Friendship.objects.filter(status="accepted", friend_id=pid).values("user_id")
    return SocialProfile.objects.filter(Q(id__in=out) | Q(id__in=inn)).order_by("name")[:limit]


def get_profile(pk: int) -> SocialProfile:
    return get_object_or_404(
        SocialProfile.objects.select_related("user", "relationship_with")
        .defer("looking_for", "interested_in", "languages"),
        pk=pk,
    )


def friend_ids(profile: SocialProfile) -> set[int]:
    out, inn = Friendship.objects.filter(status="accepted"), profile.id
    return set(out.filter(user_id=inn).values_list("friend_id", flat=True)) | set(
        out.filter(friend_id=inn).values_list("user_id", flat=True)
    )


def friend_count(profile: SocialProfile) -> int:
    return Friendship.objects.filter(status="accepted").filter(
        Q(user_id=profile.id) | Q(friend_id=profile.id)
    ).count()


def feed_queryset(viewer=None):
    qs = Post.objects.all()
    if viewer:
        fids = friend_ids(viewer) | {viewer.id}
        qs = qs.filter(
            Q(visibility="public")
            | Q(visibility="friends", social_user_id__in=fids)
            | Q(social_user_id=viewer.id)
        ).exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    else:
        qs = qs.filter(visibility="public")
    return (
        qs.select_related("social_user", "shared_post", "shared_post__social_user")
        .defer(
            "search_vector",
            "social_user__looking_for", "social_user__interested_in", "social_user__languages",
            "shared_post__social_user__looking_for", "shared_post__social_user__interested_in", "shared_post__social_user__languages",
        )
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages")
                .order_by("id"),
            ),
            "media",
            "poll__options",
        )
        .annotate(likes=Count("reactions", distinct=True), n_comments=Count("comments", distinct=True))
    )


def wall_owner_id(post) -> int | None:
    """Profile id whose wall this post lives on (wall notes + own wall posts)."""
    topic = getattr(post, "topic", None) or ""
    if topic.startswith("wall:"):
        try:
            return int(topic.split(":", 1)[1])
        except (TypeError, ValueError):
            return None
    return getattr(post, "social_user_id", None)


def can_manage_wall_post(me, post) -> bool:
    """Author or wall owner may remove the post (classic FB)."""
    if not me or not post:
        return False
    if post.social_user_id == me.id:
        return True
    oid = wall_owner_id(post)
    return bool(oid and oid == me.id)


def can_manage_wall_comment(me, comment) -> bool:
    if not me or not comment:
        return False
    if comment.social_user_id == me.id:
        return True
    post = comment.post
    return can_manage_wall_post(me, post)


def wall_posts_for(profile, limit=20, viewer=None):
    """Own wall posts + notes on this wall. No status / polls (classic Profile Wall)."""
    key = f"wall:{profile.id}"
    qs = (
        Post.objects.filter(Q(topic=key) | (Q(social_user=profile) & ~Q(topic__startswith="wall:")))
        .exclude(kind="status")
        .exclude(topic="status")
        .exclude(topic="picture")
        .select_related("social_user")
        .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages", "search_vector")
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages").order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )
    if viewer and viewer.id == profile.id:
        pass
    elif viewer:
        friend = profile.id in friend_ids(viewer)
        vis = Q(visibility="public") | Q(social_user=viewer)
        if friend:
            vis |= Q(visibility="friends") | Q(visibility="")
        qs = qs.filter(vis).exclude(visibility="private")
        qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    else:
        qs = qs.filter(Q(visibility="public") | Q(visibility="")).exclude(visibility="private")
    return qs.order_by("-id")[:limit]


def mini_feed(profile, limit=8, viewer=None):
    """FB Mini-Feed: recent activity of one person (respects viewer)."""
    from apps.social.models import Photo
    from apps.social.profile_page import can_view_wall, is_friend

    own = bool(viewer and viewer.id == profile.id)
    relation = None
    if viewer and not own:
        relation = Friendship.objects.filter(
            Q(user=viewer, friend=profile) | Q(user=profile, friend=viewer)
        ).first()
    friends = own or is_friend(relation)
    show_wall = can_view_wall(viewer, profile, relation)

    items = []
    wall_ids = set()
    for p in Post.objects.filter(social_user=profile).order_by("-id")[:limit]:
        if not own:
            vis = p.visibility or "public"
            if vis == "private":
                continue
            if vis == "friends" and not friends:
                continue
        topic = p.topic or ""
        if p.kind == "status" or topic == "status":
            kind = "status"
        elif topic == "picture":
            kind = "picture"
        elif topic.startswith("wall:"):
            oid = wall_owner_id(p)
            if oid and oid != profile.id:
                kind = "wall"
                wall_ids.add(oid)
            else:
                kind = "post"
        else:
            kind = "post"
        if kind in ("wall", "post") and not show_wall:
            continue
        row = {"kind": kind, "at": p.created_at, "post": p}
        if kind == "wall":
            row["wall_id"] = oid
        items.append(row)
    if friends or own:
        for m in CommunityMember.objects.filter(social_user=profile).select_related("community").order_by("-id")[:limit]:
            items.append({"kind": "joined", "at": m.created_at, "group": m.community})
        for g in Community.objects.filter(creator=profile).order_by("-id")[:4]:
            items.append({"kind": "created", "at": g.created_at, "group": g})
        for ph in (
            Photo.objects.filter(album__social_user=profile).exclude(path="")
            .select_related("album").order_by("-id")[:limit]
        ):
            items.append({"kind": "photo", "at": ph.created_at, "photo": ph, "album": ph.album})
        for f in (
            Friendship.objects.filter(status="accepted")
            .filter(Q(user=profile) | Q(friend=profile))
            .select_related("user", "friend")
            .order_by("-updated_at", "-id")[:limit]
        ):
            other = f.friend if f.user_id == profile.id else f.user
            items.append({"kind": "friend", "at": f.updated_at or f.created_at, "other": other})
    if wall_ids:
        names = dict(SocialProfile.objects.filter(id__in=wall_ids).values_list("id", "name"))
        for it in items:
            if it.get("wall_id"):
                it["wall_name"] = names.get(it["wall_id"])
    items.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    return items[:limit]


def _visible_group_q(member_ids):
    return Q(community__privacy="public") | Q(community_id__in=member_ids) | Q(community__privacy="")


def _add_group_posts(items, blocked, member_ids, limit):
    from apps.social.models import CommunityPost, Photo
    qs = (
        CommunityPost.objects.select_related("social_user", "community")
        .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages")
        .prefetch_related("poll__options", "media")
        .annotate(likes=Count("reactions", distinct=True), n_comments=Count("comments", distinct=True))
        .filter(_visible_group_q(member_ids))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for p in qs[:limit]:
        items.append({"kind": "group_post", "at": p.created_at, "post": p, "actor": p.social_user, "group": p.community})


def _add_joins(items, blocked, member_ids, limit):
    qs = (
        CommunityMember.objects.select_related("social_user", "community")
        .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages")
        .filter(_visible_group_q(member_ids))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for m in qs[:limit]:
        items.append({"kind": "joined", "at": m.created_at, "actor": m.social_user, "group": m.community})


def _add_created(items, blocked, member_ids):
    qs = Community.objects.select_related("creator").filter(creator__isnull=False).order_by("-id")
    if blocked:
        qs = qs.exclude(creator_id__in=blocked)
    for g in qs[:20]:
        if g.privacy == "closed" and g.id not in member_ids:
            continue
        items.append({"kind": "created", "at": g.created_at, "actor": g.creator, "group": g})


def _add_photos(items, blocked, limit):
    from apps.social.models import Photo
    qs = (
        Photo.objects.select_related("album", "album__social_user")
        .exclude(path__isnull=True).exclude(path="")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(album__social_user_id__in=blocked)
    for ph in qs[:limit]:
        items.append({
            "kind": "photos", "at": ph.created_at, "photo": ph,
            "actor": ph.album.social_user, "album": ph.album,
        })


def news_items(viewer=None, limit=40):
    """FB-2006 News Feed: wall + group activity, newest first."""
    from django.core.cache import cache
    key = f"news:{getattr(viewer, 'id', 0)}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    items = []
    blocked = (
        list(Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True)) if viewer else []
    )
    member_ids = set(
        CommunityMember.objects.filter(social_user=viewer).values_list("community_id", flat=True)
    ) if viewer else set()
    for p in feed_queryset(viewer)[:limit]:
        items.append({"kind": "wall", "at": p.created_at, "post": p, "actor": p.social_user})
    _add_group_posts(items, blocked, member_ids, limit)
    _add_joins(items, blocked, member_ids, limit)
    _add_created(items, blocked, member_ids)
    _add_photos(items, blocked, limit)
    items.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    items = items[:limit]
    cache.set(key, items, 20)
    return items


def shared_with(viewer, limit=6):
    """Right-rail: recent posts from joined groups."""
    if not viewer:
        return []
    ids = CommunityMember.objects.filter(social_user=viewer).values("community_id")
    return list(
        CommunityPost.objects.filter(community_id__in=ids)
        .exclude(social_user=viewer)
        .select_related("social_user", "community")
        .defer("social_user__looking_for", "social_user__interested_in", "social_user__languages")
        .order_by("-id")[:limit]
    )


def upcoming_birthdays(viewer=None, days=14):
    today = timezone.localdate()
    end = today + timedelta(days=days)
    qs = SocialProfile.objects.exclude(birthday__isnull=True).only(
        "id", "name", "slug", "birthday", "avatar_path", "avatar_color",
    )
    if viewer:
        qs = qs.filter(id__in=friend_ids(viewer) | {viewer.id})
    out = []
    for p in qs[:200]:
        b = p.birthday.replace(year=today.year)
        if b < today:
            b = b.replace(year=today.year + 1)
        if today <= b <= end:
            out.append((b, p))
    out.sort(key=lambda x: x[0])
    return out[:12]
