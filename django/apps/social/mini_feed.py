"""FB Mini-Feed — short builders; services.mini_feed re-exports."""
from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.social.models import Friendship, Post, SocialProfile


def _visible(post, *, own, friends) -> bool:
    if own:
        return True
    vis = post.visibility or "public"
    if vis == "private":
        return False
    if vis == "friends" and not friends:
        return False
    return True


def _post_kind_row(p, profile, wall_ids: set) -> tuple[dict | None, Post | None]:
    """Return (item, gift_post_or_None). Skip → (None, None)."""
    topic = p.topic or ""
    if p.kind == "status" or topic == "status":
        return {"kind": "status", "at": p.created_at, "post": p}, None
    if p.kind == "note" or topic == "note":
        return {"kind": "note", "at": p.created_at, "post": p}, None
    if p.kind in ("link", "video"):
        from apps.social.classic_extra import hydrate_posted
        hydrate_posted(p)
        return {"kind": p.kind, "at": p.created_at, "post": p}, None
    if topic == "picture":
        return {"kind": "picture", "at": p.created_at, "post": p}, None
    if topic.startswith("page:") or topic.startswith("event:"):
        return None, None
    if topic.startswith("gift:") or p.kind == "gift":
        from apps.social.gifts import recipient_id_from_topic
        rid = recipient_id_from_topic(topic)
        row = {"kind": "gift_sent", "at": p.created_at, "post": p}
        if rid:
            wall_ids.add(rid)
            row["gift_to_id"] = rid
        return row, p
    if topic.startswith("wall:"):
        from apps.social.services import wall_owner_id
        oid = wall_owner_id(p)
        if oid and oid != profile.id:
            wall_ids.add(oid)
            return {"kind": "wall", "at": p.created_at, "post": p, "wall_id": oid}, None
        return {"kind": "post", "at": p.created_at, "post": p}, None
    return {"kind": "post", "at": p.created_at, "post": p}, None


def _side_items(profile, limit: int) -> list[dict]:
    from apps.social.mini_feed_side import _side_items as build
    return build(profile, limit)


def _fill_names(items: list[dict], wall_ids: set) -> None:
    if not wall_ids:
        return
    names = dict(SocialProfile.objects.filter(id__in=wall_ids).values_list("id", "name"))
    for it in items:
        if it.get("wall_id"):
            it["wall_name"] = names.get(it["wall_id"])
        if it.get("gift_to_id"):
            it["gift_to_name"] = names.get(it["gift_to_id"])


def build_mini_feed(profile, limit=8, viewer=None) -> list[dict]:
    from apps.social.gifts import attach_stickers
    from apps.social.profile_page import can_view_wall, is_friend

    own = bool(viewer and viewer.id == profile.id)
    relation = None
    if viewer and not own:
        relation = Friendship.objects.filter(
            Q(user=viewer, friend=profile) | Q(user=profile, friend=viewer)
        ).first()
    friends = own or is_friend(relation)
    show_wall = can_view_wall(viewer, profile, relation)

    items, wall_ids, gifts = [], set(), []
    for p in (
        Post.objects.filter(social_user=profile)
        .defer("mood", "emoji", "search_vector")
        .order_by("-id")[:limit]
    ):
        if not _visible(p, own=own, friends=friends):
            continue
        row, gift = _post_kind_row(p, profile, wall_ids)
        if not row:
            continue
        if row["kind"] == "gift_sent":
            if friends or own:
                items.append(row)
                gifts.append(gift)
            continue
        if row["kind"] in ("wall", "post", "note", "link", "video") and not show_wall:
            continue
        items.append(row)

    if gifts:
        attach_stickers(gifts)
        for it in items:
            if it.get("kind") == "gift_sent":
                it["sticker"] = getattr(it["post"], "gift_sticker", None)

    if friends or own:
        items.extend(_side_items(profile, limit))
    _fill_names(items, wall_ids)
    items.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    return items[:limit]
