"""News Feed story builders — news_feed imports these; services stays lean."""
from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Q

from apps.social.models import (
    GROUP_POST_DEFER, POST_DEFER, Community, CommunityMember, CommunityPost,
    Friendship, OgStory, Post, SocialProfile, TimelineMilestone, profile_related,
)
from apps.social.services import attach_pages, feed_queryset, post_visible_q


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


def _og_label(verb: str) -> str:
    from apps.social.era2011 import og_label
    return og_label(verb)


def _add_og(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        OgStory.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "og", "at": row.created_at, "actor": row.social_user,
            "og": row, "verb": row.verb, "verb_label": _og_label(row.verb),
        })


def _add_milestones(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        TimelineMilestone.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-occurred_on", "-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "milestone",
            "at": row.created_at or datetime.combine(row.occurred_on, datetime.min.time()),
            "actor": row.social_user, "milestone": row,
        })


def _add_follow_public(items, viewer, blocked, follows, limit):
    """Public posts from people you Subscribe to (not already in friend circle)."""
    if not viewer or not follows:
        return
    from apps.social.models import Post, POST_DEFER
    from apps.social.services import attach_wall_notes

    qs = (
        Post.objects.filter(social_user_id__in=follows)
        .filter(Q(visibility="public") | Q(visibility=""))
        .exclude(kind__in=("gift", "poll"))
        .exclude(topic__startswith="gift:")
        .exclude(topic__startswith="page:")
        .exclude(topic__startswith="event:")
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    posts = list(qs[:limit])
    attach_wall_notes(posts)
    for p in posts:
        topic = p.topic or ""
        if p.kind == "status" or topic == "status":
            kind = "status"
        elif topic == "picture":
            kind = "picture"
        elif p.kind == "note":
            kind = "note"
        elif p.kind in ("link", "video", "share"):
            kind = p.kind
        else:
            kind = "wall"
        items.append({"kind": kind, "at": p.created_at, "post": p, "actor": p.social_user})
    # OG from followees
    oqs = (
        OgStory.objects.filter(social_user_id__in=follows)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        oqs = oqs.exclude(social_user_id__in=blocked)
    for row in oqs[:limit]:
        items.append({
            "kind": "og", "at": row.created_at, "actor": row.social_user,
            "og": row, "verb": row.verb, "verb_label": _og_label(row.verb),
        })


