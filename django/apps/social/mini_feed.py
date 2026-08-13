"""FB Mini-Feed — short builders; services.mini_feed re-exports."""
from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.social.models import (
    Community, CommunityMember, Friendship, Post, SocialProfile,
)


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
    from apps.social.models import CompanyFollower, OgStory, Photo, PhotoTag
    from apps.social.era2011 import og_label
    from apps.social.gifts import attach_stickers, gifts_for

    out = []
    for m in (
        CommunityMember.objects.filter(social_user=profile)
        .select_related("community").order_by("-id")[:limit]
    ):
        out.append({"kind": "joined", "at": m.created_at, "group": m.community})
    for g in Community.objects.filter(creator=profile).order_by("-id")[:4]:
        out.append({"kind": "created", "at": g.created_at, "group": g})
    for fan in (
        CompanyFollower.objects.filter(social_user=profile)
        .select_related("company").order_by("-id")[:limit]
    ):
        out.append({"kind": "fan", "at": fan.created_at, "page": fan.company})
    for ph in (
        Photo.objects.filter(album__social_user=profile).exclude(path="")
        .select_related("album").order_by("-id")[:limit]
    ):
        out.append({"kind": "photo", "at": ph.created_at, "photo": ph, "album": ph.album})
    for tag in (
        PhotoTag.objects.filter(social_user=profile, status="approved")
        .select_related("photo", "photo__album", "tagged_by")
        .order_by("-id")[:limit]
    ):
        out.append({
            "kind": "tagged", "at": tag.created_at, "photo": tag.photo,
            "album": tag.photo.album, "by": tag.tagged_by,
        })
    for f in (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user=profile) | Q(friend=profile))
        .select_related("user", "friend")
        .order_by("-updated_at", "-id")[:limit]
    ):
        other = f.friend if f.user_id == profile.id else f.user
        out.append({"kind": "friend", "at": f.updated_at or f.created_at, "other": other})
    for og in OgStory.objects.filter(social_user=profile).order_by("-id")[:limit]:
        out.append({
            "kind": "og", "at": og.created_at, "og": og,
            "verb_label": og_label(og.verb),
        })
    for gp in attach_stickers(gifts_for(profile, limit=limit)):
        out.append({
            "kind": "gift_got", "at": gp.created_at, "post": gp,
            "from": gp.social_user, "sticker": getattr(gp, "gift_sticker", None),
        })
    return out


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
