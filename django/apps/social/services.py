from datetime import datetime, timedelta

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.social.models import (
    GROUP_POST_DEFER, POST_DEFER, PROFILE_DEFER, Block, Comment, Community,
    CommunityMember, CommunityPost, Friendship, Post, SocialProfile, profile_related,
)


def now():
    t = timezone.now()
    return timezone.make_naive(t) if timezone.is_aware(t) else t


def profile_of(user) -> SocialProfile | None:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, "profile", None) or SocialProfile.objects.filter(user_id=user.id).first()


def accepted_friends(profile: SocialProfile, limit=None):
    """Owner's friends by name (unsliced QS — chain .exclude/.filter, then slice)."""
    pid = profile.id
    out = Friendship.objects.filter(status="accepted", user_id=pid).values("friend_id")
    inn = Friendship.objects.filter(status="accepted", friend_id=pid).values("user_id")
    qs = SocialProfile.objects.filter(Q(id__in=out) | Q(id__in=inn)).order_by("name")
    return qs[:limit] if limit is not None else qs


def get_profile(pk: int) -> SocialProfile:
    return get_object_or_404(
        SocialProfile.objects.select_related("user", "relationship_with").defer(*PROFILE_DEFER),
        pk=pk,
    )


def friend_ids(profile: SocialProfile) -> set[int]:
    out, inn = Friendship.objects.filter(status="accepted"), profile.id
    return set(out.filter(user_id=inn).values_list("friend_id", flat=True)) | set(
        out.filter(friend_id=inn).values_list("user_id", flat=True)
    )


def friend_count(profile: SocialProfile) -> int:
    """Unique friends — DB stores accepted edges both ways (A→B and B→A)."""
    return len(friend_ids(profile))


def post_visible_q(viewer, *, author_field="social_user_id") -> Q:
    """Public / friends-of-author / friends-of-wall-owner / own. Empty visibility ≡ public."""
    if not viewer:
        return Q(visibility="public") | Q(visibility="")
    fids = friend_ids(viewer) | {viewer.id}
    af = author_field
    wall_topics = [f"wall:{i}" for i in fids]
    return (
        Q(visibility="public") | Q(visibility="")
        | Q(visibility="friends", **{f"{af}__in": fids})
        | Q(visibility="friends", topic__in=wall_topics)
        | Q(**{af: viewer.id})
    )


def feed_queryset(viewer=None):
    """Posts the viewer may open (permalink / comment). Not the News Feed circle."""
    qs = Post.objects.filter(post_visible_q(viewer)).exclude(kind__in=("status", "picture", "poll", "share"))
    if viewer:
        qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    return (
        qs.select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__"))
                .order_by("id"),
            ),
            "media",
        )
        .annotate(n_comments=Count("comments", distinct=True))
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


def _comment_host(me, comment, *, host_id=None, admin=False) -> bool:
    """Author, wall/album host, or group admin may remove a flat comment."""
    if not me or not comment:
        return False
    return comment.social_user_id == me.id or (host_id and host_id == me.id) or bool(admin)


def can_manage_wall_comment(me, comment) -> bool:
    post = getattr(comment, "post", None)
    return _comment_host(me, comment, host_id=wall_owner_id(post) if post else None) or (
        can_manage_wall_post(me, post) if post else False
    )


def is_group_admin(me, group) -> bool:
    from apps.social.group_page import ADMIN_ROLES
    return bool(
        me and group
        and CommunityMember.objects.filter(community=group, social_user=me, role__in=ADMIN_ROLES).exists()
    )


def can_manage_group_comment(me, comment, group=None) -> bool:
    g = group or getattr(getattr(comment, "post", None), "community", None)
    return _comment_host(me, comment, admin=is_group_admin(me, g))


def can_manage_photo_comment(me, comment, album) -> bool:
    return _comment_host(me, comment, host_id=getattr(album, "social_user_id", None))


def wall_posts_for(profile, limit=20, viewer=None):
    """Notes on this wall (`wall:{id}`). Legacy own posts without wall topic still listed."""
    key = f"wall:{profile.id}"
    qs = (
        Post.objects.filter(
            Q(topic=key)
            | (Q(social_user=profile) & ~Q(topic__startswith="wall:"))
        )
        .exclude(kind__in=("status", "picture", "poll", "share", "note"))
        .exclude(topic__in=("status", "picture", "note"))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )
    if viewer and viewer.id == profile.id:
        pass  # owner sees private notes too
    else:
        qs = qs.filter(post_visible_q(viewer))
        if viewer:
            qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    return qs.order_by("-id")[:limit]


def notes_for(profile, limit=20, viewer=None):
    """FB Notes — authored notes (kind=note), classic mid-2006 tab."""
    qs = (
        Post.objects.filter(social_user=profile, kind="note")
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
    )
    if not (viewer and viewer.id == profile.id):
        qs = qs.filter(post_visible_q(viewer))
        if viewer:
            qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    return list(qs.order_by("-id")[:limit])


def wall_to_wall(a, b, limit=40, viewer=None):
    """FB Wall-to-Wall: notes exchanged between two profiles."""
    qs = (
        Post.objects.filter(
            Q(topic=f"wall:{a.id}", social_user=b) | Q(topic=f"wall:{b.id}", social_user=a)
        )
        .exclude(kind__in=("status", "picture", "poll", "share", "note"))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
        .filter(post_visible_q(viewer))
        .order_by("-id")
    )
    if viewer:
        qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    posts = list(qs[:limit])
    attach_wall_notes(posts)
    return posts


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
        elif p.kind == "note" or topic == "note":
            kind = "note"
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
        if kind in ("wall", "post", "note") and not show_wall:
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


def attach_wall_notes(posts):
    """Mark cross-wall notes for News Feed attribution (flat, no extra queries in template)."""
    need = set()
    for p in posts:
        topic = getattr(p, "topic", None) or ""
        wid = wall_owner_id(p) if topic.startswith("wall:") else None
        if wid and wid != p.social_user_id:
            need.add(wid)
            p._wall_note_id = wid
        else:
            p._wall_note_id = None
    owners = SocialProfile.objects.in_bulk(need) if need else {}
    for p in posts:
        p.wall_note_owner = owners.get(p._wall_note_id) if p._wall_note_id else None


def _add_group_posts(items, blocked, member_ids, limit):
    """Only groups the viewer belongs to (classic News Feed)."""
    if not member_ids:
        return
    qs = (
        CommunityPost.objects.select_related("social_user", "community")
        .defer(*GROUP_POST_DEFER, *profile_related("social_user__"))
        .prefetch_related("media")
        .annotate(n_comments=Count("comments", distinct=True))
        .filter(community_id__in=member_ids)
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for p in qs[:limit]:
        items.append({"kind": "group_post", "at": p.created_at, "post": p, "actor": p.social_user, "group": p.community})


def _add_joins(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        CommunityMember.objects.select_related("social_user", "community")
        .defer(*profile_related("social_user__"))
        .filter(social_user_id__in=fids)
        .exclude(community__privacy="closed")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for m in qs[:limit]:
        items.append({"kind": "joined", "at": m.created_at, "actor": m.social_user, "group": m.community})


def _add_created(items, blocked, fids):
    if not fids:
        return
    qs = (
        Community.objects.select_related("creator")
        .filter(creator_id__in=fids)
        .exclude(privacy="closed")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(creator_id__in=blocked)
    for g in qs[:20]:
        items.append({"kind": "created", "at": g.created_at, "actor": g.creator, "group": g})


def _add_photos(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import Photo
    qs = (
        Photo.objects.select_related("album", "album__social_user")
        .filter(album__social_user_id__in=fids)
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


def bump_news():
    """Invalidate News Feed cache for every viewer (posts/comments change)."""
    from django.core.cache import cache
    try:
        cache.incr("news:ver")
    except ValueError:
        cache.set("news:ver", 1, None)


def news_items(viewer=None, limit=40):
    """FB-2006 News Feed: friends' circle + own groups. Status/picture → Mini-Feed."""
    from django.core.cache import cache
    ver = cache.get("news:ver") or 0
    key = f"news:{getattr(viewer, 'id', 0)}:{limit}:v{ver}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    items = []
    fids = (friend_ids(viewer) | {viewer.id}) if viewer else set()
    blocked = (
        list(Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True)) if viewer else []
    )
    member_ids = set(
        CommunityMember.objects.filter(social_user=viewer).values_list("community_id", flat=True)
    ) if viewer else set()
    wall_topics = [f"wall:{i}" for i in fids]
    posts = list(
        feed_queryset(viewer)
        .filter(Q(social_user_id__in=fids) | Q(topic__in=wall_topics))
        .exclude(topic__in=("status", "picture"))[:limit]
    ) if fids else []
    attach_wall_notes(posts)
    for p in posts:
        if getattr(p, "kind", None) == "note":
            items.append({"kind": "note", "at": p.created_at, "post": p, "actor": p.social_user})
        else:
            items.append({"kind": "wall", "at": p.created_at, "post": p, "actor": p.social_user})
    _add_group_posts(items, blocked, member_ids, limit)
    _add_joins(items, blocked, fids, limit)
    _add_created(items, blocked, fids)
    _add_photos(items, blocked, fids, limit)
    items.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    items = items[:limit]
    cache.set(key, items, 20)
    return items


def group_updates(viewer, limit=6):
    """Right-rail: recent posts from joined groups."""
    if not viewer:
        return []
    ids = CommunityMember.objects.filter(social_user=viewer).values("community_id")
    return list(
        CommunityPost.objects.filter(community_id__in=ids)
        .exclude(social_user=viewer)
        .select_related("social_user", "community")
        .defer(*GROUP_POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")[:limit]
    )


def feed_rail(viewer):
    """Home right column — requests, pokes, events, groups, birthdays (FB 2006)."""
    from django.db.models import Count, Q

    from apps.social import events as ev
    from apps.social import friendship as fr
    from apps.social.models import Community, Notification

    pending = fr.annotate_mutuals(viewer, list(fr.pending_to(viewer)[:8])) if viewer else []
    popular = list(
        Community.objects.annotate(n=Count("memberships", distinct=True))
        .filter(Q(privacy="public") | Q(privacy=""))
        .order_by("-n", "name")[:6]
    )
    pokes = []
    if viewer:
        from apps.social.notify import attach_poker_ids
        pokes = attach_poker_ids(list(
            Notification.objects.filter(social_user=viewer, type="poke", seen=False)
            .order_by("-id")[:6]
        ))
    rail_events = list(ev.list_events(viewer, "upcoming")[:5]) if viewer else []
    event_invites = (
        Notification.objects.filter(social_user=viewer, type="event_invite", seen=False).count()
        if viewer else 0
    )
    return {
        "requests": pending,
        "pokes": pokes,
        "rail_events": rail_events,
        "event_invites": event_invites,
        "popular_groups": popular,
        "group_posts": group_updates(viewer),
        "birthdays": upcoming_birthdays(viewer),
    }


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
