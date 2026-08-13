"""News Feed assembly — short builders; services.news_items re-exports."""
from __future__ import annotations

from django.db.models import Q

from apps.social.models import Block, CommunityMember
from apps.social.services import (
    _add_anniversaries, _add_checkins, _add_created, _add_event_created,
    _add_event_going, _add_event_posts, _add_friends, _add_gifts, _add_group_docs,
    _add_group_posts, _add_joins, _add_likes, _add_market, _add_page_fans,
    _add_page_posts, _add_photo_likes, _add_photo_tags, _add_photos, _add_polls,
    _add_questions, _add_relationships, _add_reviews, _add_status_picture,
    _feed_at, attach_wall_notes, feed_queryset, friend_ids,
)


def _scope(viewer):
    from apps.social.models import CompanyFollower
    fids = (friend_ids(viewer) | {viewer.id}) if viewer else set()
    blocked = (
        list(Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True))
        if viewer else []
    )
    member_ids = set(
        CommunityMember.objects.filter(social_user=viewer).values_list("community_id", flat=True)
    ) if viewer else set()
    page_ids = set(
        CompanyFollower.objects.filter(social_user=viewer).values_list("company_id", flat=True)
    ) if viewer else set()
    return fids, blocked, member_ids, page_ids


def _wall_stories(items, viewer, fids, limit):
    if not fids:
        return
    wall_topics = [f"wall:{i}" for i in fids]
    posts = list(
        feed_queryset(viewer)
        .filter(Q(social_user_id__in=fids) | Q(topic__in=wall_topics))
        .exclude(topic__in=("status", "picture"))
        .exclude(topic__startswith="page:")
        .exclude(topic__startswith="event:")
        .exclude(topic__startswith="gift:")
        .exclude(topic__startswith="place:")
        .exclude(kind__in=("gift", "checkin"))[:limit]
    )
    attach_wall_notes(posts)
    for p in posts:
        kind = getattr(p, "kind", None) or ""
        if kind == "note":
            items.append({"kind": "note", "at": p.created_at, "post": p, "actor": p.social_user})
        elif kind == "share":
            items.append({
                "kind": "share", "at": p.created_at, "post": p, "actor": p.social_user,
                "shared": getattr(p, "shared_post", None),
            })
        elif kind in ("link", "video"):
            from apps.social.classic_extra import hydrate_posted
            hydrate_posted(p)
            items.append({"kind": kind, "at": p.created_at, "post": p, "actor": p.social_user})
        else:
            items.append({"kind": "wall", "at": p.created_at, "post": p, "actor": p.social_user})


def _extra_stories(items, viewer, fids, blocked, member_ids, page_ids, limit):
    _add_group_posts(items, blocked, member_ids, limit)
    _add_joins(items, blocked, fids, limit)
    _add_created(items, blocked, fids)
    _add_photos(items, blocked, fids, limit)
    _add_page_posts(items, viewer, page_ids, blocked, limit)
    _add_page_fans(items, blocked, fids, limit)
    _add_gifts(items, viewer, fids, blocked, limit)
    _add_event_posts(items, viewer, fids, blocked, limit)
    _add_photo_tags(items, blocked, fids, limit)
    _add_event_created(items, blocked, fids, limit)
    _add_event_going(items, blocked, fids, limit)
    _add_market(items, blocked, fids, limit)
    _add_checkins(items, blocked, fids, limit)
    _add_questions(items, blocked, fids, limit)
    _add_likes(items, blocked, fids, limit)
    _add_reviews(items, blocked, fids, limit)
    _add_polls(items, blocked, fids, limit)
    _add_photo_likes(items, blocked, fids, limit)
    _add_anniversaries(items, viewer, blocked, fids, limit)
    _add_group_docs(items, blocked, member_ids, limit)
    _add_status_picture(items, viewer, blocked, fids, limit)
    _add_friends(items, blocked, fids, limit)
    _add_relationships(items, blocked, fids, limit)
    from apps.social import era2011 as e11
    e11._add_og(items, blocked, fids, limit)
    e11._add_milestones(items, blocked, fids, limit)
    follows = e11.followee_ids(viewer) - fids if viewer else set()
    e11._add_follow_public(items, viewer, blocked, follows, limit)
    from apps.social import era2012 as e12
    e12._add_page_milestones(items, viewer, page_ids, blocked, limit)
    e12._add_collections(items, blocked, fids, limit)
    from apps.social import era2013 as e13
    e13._add_hashtag_stories(items, blocked, fids, limit)
    from apps.social import era2014 as e14
    e14._add_safety_stories(items, blocked, fids, limit)


def _finalize(items, viewer, limit):
    items.sort(key=lambda x: _feed_at(x.get("at")), reverse=True)
    items = items[: limit * 2]
    if viewer:
        from apps.social import feed_hide as fh
        items = fh.filter_items(viewer, items)
    return items[:limit]


def build_news_items(viewer=None, limit=40):
    """FB-2006 News Feed: friends' circle + groups + fanned pages + gifts."""
    from django.core.cache import cache

    ver = cache.get("news:ver") or 0
    key = f"news:{getattr(viewer, 'id', 0)}:{limit}:v{ver}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    fids, blocked, member_ids, page_ids = _scope(viewer)
    items = []
    _wall_stories(items, viewer, fids, limit)
    _extra_stories(items, viewer, fids, blocked, member_ids, page_ids, limit)
    items = _finalize(items, viewer, limit)
    cache.set(key, items, 20)
    return items
