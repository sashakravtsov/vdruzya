from datetime import date, datetime, timedelta

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


def _feed_at(value):
    """Normalize feed story timestamps so date/datetime mix never breaks sort."""
    if value is None:
        return datetime.min
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return datetime.min


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
    # Load Info-tab JSON fields; keep other PROFILE_DEFER leftovers off the row.
    info_ok = ("looking_for", "interested_in", "languages")
    defer = tuple(f for f in PROFILE_DEFER if f not in info_ok)
    return get_object_or_404(
        SocialProfile.objects.select_related("user", "relationship_with").defer(*defer),
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
    qs = Post.objects.filter(post_visible_q(viewer)).exclude(kind__in=("status", "picture", "poll"))
    if viewer:
        qs = qs.exclude(social_user_id__in=Block.objects.filter(blocker=viewer).values("blocked_id"))
    return (
        qs.select_related("social_user", "shared_post", "shared_post__social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"), *profile_related("shared_post__social_user__"))
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
    """Author, wall owner, gift recipient, or page admin may remove the post (classic FB)."""
    if not me or not post:
        return False
    if post.social_user_id == me.id:
        return True
    oid = wall_owner_id(post)
    if oid and oid == me.id:
        return True
    topic = getattr(post, "topic", None) or ""
    if topic.startswith("gift:"):
        try:
            return int(topic.split(":", 1)[1]) == me.id
        except (TypeError, ValueError):
            return False
    if topic.startswith("page:"):
        try:
            pid = int(topic.split(":", 1)[1])
        except (TypeError, ValueError):
            return False
        from apps.social.models import CompanyAdmin
        return CompanyAdmin.objects.filter(company_id=pid, social_user=me).exists()
    if topic.startswith("event:"):
        try:
            eid = int(topic.split(":", 1)[1])
        except (TypeError, ValueError):
            return False
        from apps.social.models import Event
        return Event.objects.filter(pk=eid, host_id=me.id).exists()
    return False


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


def wall_posts_for(profile, limit=20, viewer=None, wall_filter="all"):
    """Notes on this wall — builders in wall_posts.wall_posts_for."""
    from apps.social.wall_posts import wall_posts_for as build
    return build(profile, limit=limit, viewer=viewer, wall_filter=wall_filter)


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
    """FB Mini-Feed — implemented in mini_feed.build_mini_feed (keep import stable)."""
    from apps.social.mini_feed import build_mini_feed
    return build_mini_feed(profile, limit=limit, viewer=viewer)


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
    from apps.social.classic_extra import hydrate_posted
    for p in qs[:limit]:
        if getattr(p, "kind", None) == "video":
            hydrate_posted(p)
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


def _page_id_from_topic(topic) -> int | None:
    topic = topic or ""
    if not topic.startswith("page:"):
        return None
    try:
        return int(topic.split(":", 1)[1])
    except (TypeError, ValueError):
        return None


def attach_pages(posts):
    """Attach Company objects for page:{id} wall posts."""
    from apps.social.models import Company
    need = set()
    for p in posts:
        pid = _page_id_from_topic(getattr(p, "topic", None))
        p._page_id = pid
        if pid:
            need.add(pid)
    pages = Company.objects.in_bulk(need) if need else {}
    for p in posts:
        p.page = pages.get(getattr(p, "_page_id", None))


def _add_page_posts(items, viewer, page_ids, blocked, limit):
    """News from Pages the viewer fans — attributed to the Page, not only the admin."""
    if not viewer or not page_ids:
        return
    topics = [f"page:{pid}" for pid in page_ids]
    qs = (
        feed_queryset(viewer)
        .filter(topic__in=topics)
        .exclude(kind__in=("note", "gift"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    from apps.social.classic_extra import hydrate_posted
    posts = list(qs[:limit])
    attach_pages(posts)
    for p in posts:
        if not getattr(p, "page", None):
            continue
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
        items.append({
            "kind": "page_post", "at": p.created_at, "post": p,
            "actor": p.social_user, "page": p.page,
        })


def _add_page_fans(items, blocked, fids, limit):
    """Friends became fans of a Page."""
    if not fids:
        return
    from apps.social.models import CompanyFollower
    qs = (
        CompanyFollower.objects.select_related("social_user", "company")
        .defer(*profile_related("social_user__"))
        .filter(social_user_id__in=fids)
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "fan", "at": row.created_at,
            "actor": row.social_user, "page": row.company,
        })


def _add_gifts(items, viewer, fids, blocked, limit):
    """Friends sent/received gifts — still never on personal walls."""
    if not viewer or not fids:
        return
    from apps.social.gifts import attach_stickers, recipient_id_from_topic
    gift_topics = [f"gift:{i}" for i in fids]
    # Do not defer sticker — gift tiles need the slug.
    qs = (
        Post.objects.filter(kind="gift")
        .filter(Q(social_user_id__in=fids) | Q(topic__in=gift_topics))
        .filter(post_visible_q(viewer))
        .select_related("social_user")
        .defer("mood", "emoji", "search_vector", "shared_post", *profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    posts = list(qs[:limit])
    attach_stickers(posts)
    recip_ids = {recipient_id_from_topic(p.topic) for p in posts}
    recip_ids.discard(None)
    recipients = SocialProfile.objects.in_bulk(recip_ids) if recip_ids else {}
    for p in posts:
        rid = recipient_id_from_topic(p.topic)
        items.append({
            "kind": "gift", "at": p.created_at, "post": p,
            "actor": p.social_user,
            "recipient": recipients.get(rid),
            "sticker": getattr(p, "gift_sticker", None),
        })


def _add_event_posts(items, viewer, fids, blocked, limit):
    """Friends' posts on event walls."""
    if not viewer or not fids:
        return
    from apps.social.models import Event
    qs = (
        feed_queryset(viewer)
        .filter(social_user_id__in=fids, topic__startswith="event:")
        .exclude(kind__in=("note", "gift"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    from apps.social.classic_extra import hydrate_posted
    posts = list(qs[:limit])
    need = set()
    for p in posts:
        try:
            need.add(int((p.topic or "").split(":", 1)[1]))
        except (IndexError, ValueError):
            pass
    events = Event.objects.in_bulk(need) if need else {}
    for p in posts:
        try:
            eid = int((p.topic or "").split(":", 1)[1])
        except (IndexError, ValueError):
            continue
        event = events.get(eid)
        if not event:
            continue
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
        items.append({
            "kind": "event_post", "at": p.created_at, "post": p,
            "actor": p.social_user, "event": event,
        })


def _add_photo_tags(items, blocked, fids, limit):
    """Friend was tagged on a photo."""
    if not fids:
        return
    from apps.social.models import PhotoTag
    qs = (
        PhotoTag.objects.filter(social_user_id__in=fids, status="approved")
        .select_related("social_user", "tagged_by", "photo", "photo__album")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked).exclude(tagged_by_id__in=blocked)
    for tag in qs[:limit]:
        items.append({
            "kind": "photo_tag", "at": tag.created_at,
            "actor": tag.tagged_by or tag.social_user,
            "person": tag.social_user,
            "photo": tag.photo, "album": tag.photo.album,
        })


def _add_event_created(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import Event
    qs = (
        Event.objects.filter(host_id__in=fids)
        .select_related("host")
        .defer(*profile_related("host__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(host_id__in=blocked)
    for event in qs[:limit]:
        items.append({
            "kind": "event_created", "at": event.created_at or event.starts_at,
            "actor": event.host, "event": event,
        })


def _add_event_going(items, blocked, fids, limit):
    if not fids:
        return
    from django.db.models import F
    from apps.social.models import EventAttendee
    qs = (
        EventAttendee.objects.filter(social_user_id__in=fids, status="going")
        .exclude(social_user_id=F("event__host_id"))
        .select_related("social_user", "event")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "event_going", "at": row.updated_at or row.created_at,
            "actor": row.social_user, "event": row.event,
        })


def _add_market(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import MarketplaceListing
    qs = (
        MarketplaceListing.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "market", "at": row.created_at,
            "actor": row.social_user, "listing": row,
        })


def _add_checkins(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import PlaceCheckin
    qs = (
        PlaceCheckin.objects.filter(social_user_id__in=fids)
        .select_related("social_user", "place")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "checkin", "at": row.created_at,
            "actor": row.social_user, "place": row.place, "checkin": row,
        })


def _add_questions(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import Question
    qs = (
        Question.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "question", "at": row.created_at,
            "actor": row.social_user, "question": row,
        })


def _add_likes(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models.legacy import Reaction
    qs = (
        Reaction.objects.filter(social_user_id__in=fids, type="like")
        .select_related("social_user", "post", "post__social_user")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "like", "at": row.created_at,
            "actor": row.social_user, "post": row.post,
        })


def _add_reviews(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import PlaceReview
    qs = (
        PlaceReview.objects.filter(social_user_id__in=fids)
        .select_related("social_user", "place")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "review", "at": row.created_at,
            "actor": row.social_user, "place": row.place, "review": row,
        })


def _add_polls(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models import ClassicPoll
    qs = (
        ClassicPoll.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "poll", "at": row.created_at,
            "actor": row.social_user, "poll": row,
        })


def _add_photo_likes(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.models.legacy import PhotoReaction
    qs = (
        PhotoReaction.objects.filter(social_user_id__in=fids, type="like")
        .select_related("social_user", "photo", "photo__album")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "photo_like", "at": row.created_at,
            "actor": row.social_user, "photo": row.photo,
        })


def _add_anniversaries(items, viewer, blocked, fids, limit):
    """Today's friendship anniversaries among friends (incl. viewer)."""
    if not viewer:
        return
    from apps.social.friendship import upcoming_anniversaries
    from django.utils import timezone
    today = timezone.localdate()
    for day, years, person, since in upcoming_anniversaries(viewer, days=0, limit=limit):
        if day != today:
            continue
        if person.id in (blocked or []):
            continue
        # Synthetic "at" noon today for sort
        at = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        items.append({
            "kind": "anniversary", "at": at,
            "actor": person, "years": years, "since": since,
        })


def _add_group_docs(items, blocked, member_ids, limit):
    if not member_ids:
        return
    from apps.social.models import GroupDoc
    qs = (
        GroupDoc.objects.filter(community_id__in=member_ids)
        .select_related("social_user", "community")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "group_doc", "at": row.created_at or row.updated_at,
            "actor": row.social_user, "doc": row, "group": row.community,
        })


def _add_status_picture(items, viewer, blocked, fids, limit):
    """Status + profile-picture stories (Mini-Feed topics → News Feed)."""
    if not viewer or not fids:
        return
    qs = (
        Post.objects.filter(social_user_id__in=fids)
        .filter(Q(kind="status") | Q(topic__in=("status", "picture")))
        .filter(post_visible_q(viewer))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for p in qs[:limit]:
        topic = p.topic or ""
        if p.kind == "status" or topic == "status":
            kind = "status"
        elif topic == "picture":
            kind = "picture"
        else:
            continue
        items.append({"kind": kind, "at": p.created_at, "post": p, "actor": p.social_user})


def _add_friends(items, blocked, fids, limit):
    """«X и Y теперь друзья» — one row per accepted pair."""
    if not fids:
        return
    from django.db.models import F

    qs = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user_id__in=fids) | Q(friend_id__in=fids))
        .filter(user_id__lt=F("friend_id"))
        .select_related("user", "friend")
        .defer(*profile_related("user__"), *profile_related("friend__"))
        .order_by("-updated_at", "-id")
    )
    blocked = set(blocked or [])
    for row in qs[:limit]:
        if row.user_id in blocked or row.friend_id in blocked:
            continue
        items.append({
            "kind": "friend", "at": row.updated_at or row.created_at,
            "actor": row.user, "other": row.friend,
        })


def _add_relationships(items, blocked, fids, limit):
    """Confirmed partner relationships among friends."""
    if not fids:
        return
    from apps.social.models import RelationshipRequest

    qs = (
        RelationshipRequest.objects.filter(status="accepted")
        .filter(Q(requester_id__in=fids) | Q(partner_id__in=fids))
        .select_related("requester", "partner")
        .defer(*profile_related("requester__"), *profile_related("partner__"))
        .order_by("-updated_at", "-id")
    )
    blocked = set(blocked or [])
    for row in qs[:limit]:
        if row.requester_id in blocked or row.partner_id in blocked:
            continue
        status = (row.requester.relationship_status or "in_a_relationship")
        items.append({
            "kind": "relationship", "at": row.updated_at or row.created_at,
            "actor": row.requester, "other": row.partner, "status": status,
        })


def bump_news():
    """Invalidate News Feed cache for every viewer (posts/comments change)."""
    from django.core.cache import cache
    try:
        cache.incr("news:ver")
    except ValueError:
        cache.set("news:ver", 1, None)


def news_items(viewer=None, limit=40):
    """FB-2006 News Feed — builders in news_feed.build_news_items."""
    from apps.social.news_feed import build_news_items
    return build_news_items(viewer, limit=limit)


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


def page_updates(viewer, limit=6):
    """Right-rail: recent posts from fanned Pages."""
    if not viewer:
        return []
    from apps.social.classic_extra import hydrate_posted
    from apps.social.models import CompanyFollower
    page_ids = list(
        CompanyFollower.objects.filter(social_user=viewer).values_list("company_id", flat=True)
    )
    if not page_ids:
        return []
    topics = [f"page:{pid}" for pid in page_ids]
    posts = list(
        Post.objects.filter(topic__in=topics)
        .exclude(kind__in=("status", "picture", "poll", "share", "note", "gift"))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")[:limit]
    )
    attach_pages(posts)
    out = []
    for p in posts:
        if not getattr(p, "page", None):
            continue
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
        p.rail_text = p.snippet_text
        out.append(p)
    return out


def feed_rail(viewer):
    """Home right column — builders in feed_rail.build_feed_rail."""
    from apps.social.feed_rail import build_feed_rail
    return build_feed_rail(viewer)


def upcoming_birthdays(viewer=None, days=14, limit=12):
    today = timezone.localdate()
    end = today + timedelta(days=days)
    qs = SocialProfile.objects.exclude(birthday__isnull=True).only(
        "id", "name", "slug", "birthday", "avatar_path", "avatar_color",
    )
    if viewer:
        qs = qs.filter(id__in=friend_ids(viewer) | {viewer.id})
    out = []
    for p in qs[:400]:
        b = p.birthday.replace(year=today.year)
        if b < today:
            b = b.replace(year=today.year + 1)
        if today <= b <= end:
            out.append((b, p))
    out.sort(key=lambda x: x[0])
    return out[:limit]
