"""Graph Search builders — era2013.graph_search re-exports."""
from __future__ import annotations

from django.db.models import Q

from apps.social.era2013 import _parse_graph_q, hashtag_get, normalize_tag
from apps.social.models import Post, PostHashtag, SocialProfile, profile_related
from apps.social.services import friend_ids, post_visible_q


def _friends_qs(me):
    fids = friend_ids(me)
    return fids, SocialProfile.objects.filter(id__in=fids).defer(*profile_related()).order_by("name")


def _by_city(qs, city, limit):
    return list(qs.filter(Q(city__icontains=city) | Q(hometown__icontains=city))[:limit])


def _by_like(qs, fids, like, limit):
    from apps.social.models.legacy import Reaction
    author_ids = set(
        Reaction.objects.filter(type="like", social_user_id__in=fids)
        .filter(Q(post__body__icontains=like) | Q(post__media_label__icontains=like))
        .values_list("social_user_id", flat=True)[:200]
    )
    interest_ids = set(
        qs.filter(
            Q(interests__icontains=like)
            | Q(favorite_music__icontains=like)
            | Q(favorite_movies__icontains=like)
            | Q(favorite_books__icontains=like)
        ).values_list("id", flat=True)[:limit]
    )
    ids = list(author_ids | interest_ids)[:limit]
    by_id = SocialProfile.objects.in_bulk(ids)
    return [by_id[i] for i in ids if i in by_id]


def _by_tag(me, fids, tag, limit):
    tag_row = hashtag_get(tag)
    if not tag_row:
        return [], []
    from apps.social.models import POST_DEFER
    from apps.social.classic_extra import hydrate_posted
    author_ids = list(
        PostHashtag.objects.filter(hashtag=tag_row, post__social_user_id__in=fids)
        .values_list("post__social_user_id", flat=True)
        .distinct()[:limit]
    )
    by_id = SocialProfile.objects.in_bulk(author_ids)
    people = [by_id[i] for i in author_ids if i in by_id]
    posts = list(
        Post.objects.filter(hashtag_links__hashtag=tag_row, social_user_id__in=fids)
        .filter(post_visible_q(me))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")[:limit]
    )
    for p in posts:
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
    return people, posts


def _by_name(qs, parsed_q, q, limit):
    name_q = (parsed_q or q or "").strip()
    if name_q and not name_q.lower().startswith(("друзья", "friends")):
        return list(qs.filter(name__icontains=name_q)[:limit])
    return list(qs[:limit])


def graph_search(me, *, q="", city="", like="", tag="", limit=40):
    """Friend-network Graph Search — city / likes / hashtags + plain name."""
    if not me:
        return {"people": [], "posts": [], "parsed": {}}
    parsed = _parse_graph_q(q)
    city = (city or parsed["city"] or "").strip()
    like = (like or parsed["like"] or "").strip()
    tag = normalize_tag(tag or parsed["tag"] or "")
    fids, qs = _friends_qs(me)
    people, posts = [], []
    if city:
        people = _by_city(qs, city, limit)
    elif like:
        people = _by_like(qs, fids, like, limit)
    elif tag:
        people, posts = _by_tag(me, fids, tag, limit)
    else:
        people = _by_name(qs, parsed["q"], q, limit)
    return {
        "people": people,
        "posts": posts,
        "parsed": {"city": city, "like": like, "tag": tag, "q": q},
    }
