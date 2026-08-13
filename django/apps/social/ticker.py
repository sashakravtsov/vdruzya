"""News Feed ticker — short builders; era2011.ticker_items re-exports."""
from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.social.era2011 import followee_ids, og_label
from apps.social.models import OgStory, ProfileFollow, profile_related
from apps.social.services import friend_ids


def _post_text(p) -> str:
    topic = p.topic or ""
    if p.kind == "status" or topic == "status":
        return "обновил(а) статус"
    if topic == "picture":
        return "сменил(а) фото"
    if p.kind == "note":
        return "написал(а) заметку"
    return "написал(а) на стене"


def _from_posts(out, actors, fids, limit):
    from apps.social.models import Post
    for p in (
        Post.objects.filter(social_user_id__in=actors)
        .filter(Q(visibility="public") | Q(visibility="") | Q(social_user_id__in=fids))
        .exclude(kind="gift")
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    ):
        out.append({
            "at": p.created_at, "actor": p.social_user,
            "text": _post_text(p), "url": p.get_absolute_url(),
        })


def _from_og(out, actors, limit):
    for row in (
        OgStory.objects.filter(social_user_id__in=actors)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    ):
        out.append({
            "at": row.created_at, "actor": row.social_user,
            "text": f"{og_label(row.verb)} «{row.object_title}»",
            "url": row.object_url or f"/profile/{row.social_user_id}",
        })


def _from_follows(out, fids, blocked, viewer_id, limit):
    for row in (
        ProfileFollow.objects.filter(follower_id__in=fids)
        .exclude(followee_id=viewer_id)
        .select_related("follower", "followee")
        .defer(*profile_related("follower__"), *profile_related("followee__"))
        .order_by("-id")[:limit]
    ):
        if row.followee_id in blocked or row.follower_id in blocked:
            continue
        out.append({
            "at": row.created_at, "actor": row.follower,
            "text": f"подписался(ась) на {row.followee.name}",
            "url": f"/profile/{row.followee_id}",
        })


def ticker_items(viewer, limit=12):
    """Compact friend/follow activity for News Feed right rail (classic Ticker)."""
    if not viewer:
        return []
    from apps.social.models import Block
    fids = friend_ids(viewer) | {viewer.id}
    blocked = set(Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True))
    actors = (fids | followee_ids(viewer)) - blocked
    actors.discard(viewer.id)
    if not actors:
        return []
    out = []
    _from_posts(out, actors, fids, limit)
    _from_og(out, actors, limit)
    _from_follows(out, fids, blocked, viewer.id, limit)
    out.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    return out[:limit]
