"""FB 2013 helpers — Hashtags, Graph Search, Nearby Friends, Trending."""
from __future__ import annotations

import re
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.social.models import (
    Hashtag, Post, PostHashtag, SocialProfile, profile_related,
)
from apps.social.services import friend_ids, now, post_visible_q

_TAG_RE = re.compile(r"(?<![\w#])#([\wа-яёА-ЯЁ]{2,80})", re.UNICODE)
_CITY_RE = re.compile(
    r"(?:друзья\s+в|friends\s+in|в\s+городе)\s+([a-zA-Zа-яёА-ЯЁ\-\s]{2,40})",
    re.I | re.UNICODE,
)
_LIKE_RE = re.compile(
    r"(?:друзья\s+которым\s+нравится|friends\s+who\s+like|нравятся?)\s+(.+)$",
    re.I | re.UNICODE,
)
_TAG_Q_RE = re.compile(r"(?:#|хештег\s+|hashtag\s+)([\wа-яёА-ЯЁ]{2,80})", re.I | re.UNICODE)


def normalize_tag(raw: str) -> str:
    name = (raw or "").strip().lstrip("#").lower()
    name = re.sub(r"[^\wа-яё]", "", name, flags=re.UNICODE)
    return name[:80]


def extract_hashtags(body: str) -> list[str]:
    seen, out = set(), []
    for m in _TAG_RE.findall(body or ""):
        name = normalize_tag(m)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def sync_hashtags(post) -> list[Hashtag]:
    if not post or not getattr(post, "id", None):
        return []
    names = extract_hashtags(getattr(post, "body", "") or "")
    t = now()
    wanted = []
    for name in names:
        tag, _ = Hashtag.objects.get_or_create(name=name, defaults={"created_at": t})
        wanted.append(tag)
    want_ids = {t.id for t in wanted}
    PostHashtag.objects.filter(post=post).exclude(hashtag_id__in=want_ids).delete()
    have = set(PostHashtag.objects.filter(post=post).values_list("hashtag_id", flat=True))
    for tag in wanted:
        if tag.id not in have:
            PostHashtag.objects.create(post=post, hashtag=tag, created_at=t)
    return wanted


def hashtag_get(name: str) -> Hashtag | None:
    name = normalize_tag(name)
    if not name:
        return None
    return Hashtag.objects.filter(name=name).first()


def hashtag_posts(viewer, name: str, limit=40):
    tag = hashtag_get(name)
    if not tag:
        return tag, []
    from apps.social.models import POST_DEFER
    qs = (
        Post.objects.filter(hashtag_links__hashtag=tag)
        .filter(post_visible_q(viewer))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")
        .distinct()
    )
    from apps.social.classic_extra import hydrate_posted
    posts = list(qs[:limit])
    for p in posts:
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
    return tag, posts


def trending_topics(viewer, limit=8, hours=72):
    """Trending hashtags among friend-circle posts (classic Trending rail)."""
    since = timezone.now() - timedelta(hours=hours)
    if timezone.is_aware(since):
        since = timezone.make_naive(since)
    fids = friend_ids(viewer) | {viewer.id} if viewer else set()
    qs = (
        PostHashtag.objects.filter(created_at__gte=since)
        .filter(post__social_user_id__in=fids) if fids else PostHashtag.objects.filter(created_at__gte=since)
    )
    rows = (
        qs.values("hashtag_id", "hashtag__name")
        .annotate(n=Count("id"))
        .order_by("-n", "hashtag__name")[:limit]
    )
    return [{"name": r["hashtag__name"], "count": r["n"], "id": r["hashtag_id"]} for r in rows]


def nearby_friends(viewer, *, city=None, limit=40):
    """Friends in the same city (Nearby Friends without GPS)."""
    if not viewer:
        return [], ""
    city = (city or viewer.city or "").strip()
    fids = friend_ids(viewer)
    if not fids:
        return [], city
    qs = SocialProfile.objects.filter(id__in=fids).defer(*profile_related()).order_by("name")
    if city:
        same = list(qs.filter(Q(city__iexact=city) | Q(hometown__iexact=city))[:limit])
        if same:
            return same, city
        # partial city match
        same = list(qs.filter(Q(city__icontains=city) | Q(hometown__icontains=city))[:limit])
        return same, city
    # no city set — friends who have any city, grouped by first matches of viewer's empty
    return list(qs.exclude(city="").exclude(city__isnull=True)[:limit]), city


def _parse_graph_q(raw: str) -> dict:
    q = (raw or "").strip()
    out = {"q": q, "city": "", "like": "", "tag": ""}
    if not q:
        return out
    m = _CITY_RE.search(q)
    if m:
        out["city"] = m.group(1).strip()
    m = _LIKE_RE.search(q)
    if m:
        out["like"] = m.group(1).strip().strip("«»\"' ")
    m = _TAG_Q_RE.search(q)
    if m:
        out["tag"] = normalize_tag(m.group(1))
    return out


def graph_search(me, *, q="", city="", like="", tag="", limit=40):
    """Friend-network Graph Search — builders in graph_search.graph_search."""
    from apps.social.graph_search import graph_search as build
    return build(me, q=q, city=city, like=like, tag=tag, limit=limit)


def _add_hashtag_stories(items, blocked, fids, limit):
    if not fids:
        return
    from apps.social.classic_extra import hydrate_posted
    qs = (
        PostHashtag.objects.filter(post__social_user_id__in=fids)
        .select_related("post", "post__social_user", "hashtag")
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(post__social_user_id__in=blocked)
    seen_posts = set()
    for row in qs[: limit * 2]:
        if row.post_id in seen_posts:
            continue
        seen_posts.add(row.post_id)
        post = row.post
        if getattr(post, "kind", None) in ("link", "video"):
            hydrate_posted(post)
        items.append({
            "kind": "hashtag", "at": row.created_at or post.created_at,
            "actor": post.social_user, "post": post, "tag": row.hashtag,
        })
        if len(seen_posts) >= limit:
            break
