"""Hide people / stories from classic News Feed (FB ~2009)."""
from __future__ import annotations

from apps.social.models.legacy import FeedHide, FeedStoryHide
from apps.social.services import bump_news, now


def hidden_actor_ids(me) -> set[int]:
    if not me:
        return set()
    return set(
        FeedHide.objects.filter(social_user=me).values_list("actor_id", flat=True)
    )


def hidden_story_keys(me) -> set[str]:
    if not me:
        return set()
    return set(
        FeedStoryHide.objects.filter(social_user=me).values_list("story_key", flat=True)
    )


def _id(obj) -> int | None:
    return getattr(obj, "id", None) if obj is not None else None


# kind → item key for simple "{kind}:{id}" stories
_OBJ_KEY = {
    "safety": "checkin",
    "checkin": "checkin",
    "review": "review",
    "market": "listing",
    "group_doc": "doc",
}


def story_key_for(item: dict) -> str | None:
    """Stable per-story hide key. Kind-specific before generic post/place/event."""
    kind = (item.get("kind") or "").strip()
    actor, other = item.get("actor"), item.get("other")

    if kind == "hashtag":
        tag, post = _id(item.get("tag")), _id(item.get("post"))
        if tag and post:
            return f"hashtag:{tag}:{post}"

    if kind in _OBJ_KEY:
        oid = _id(item.get(_OBJ_KEY[kind]))
        if oid:
            return f"{kind}:{oid}"

    if kind in ("joined", "created", "fan"):
        obj = item.get("group") if kind != "fan" else item.get("page")
        oid, aid = _id(obj), _id(actor)
        if oid and aid:
            return f"{kind}:{oid}:{aid}"

    if kind == "anniversary" and _id(actor):
        years = item.get("years")
        return f"anniversary:{actor.id}:{years if years is not None else 0}"

    if kind in ("friend", "relationship"):
        a, b = _id(actor), _id(other)
        if a and b:
            lo, hi = sorted((a, b))
            return f"{kind}:{lo}:{hi}"

    if oid := _id(item.get("og")):
        return f"og:{oid}"

    if oid := _id(item.get("milestone")):
        prefix = "page_milestone" if kind == "page_milestone" else "milestone"
        return f"{prefix}:{oid}"

    if oid := _id(item.get("collection")):
        return f"collection:{oid}"

    for key, mid in (
        ("post", ""), ("photo", "photo:"), ("poll", "poll:"),
        ("question", "q:"), ("place", "place:"), ("event", "event:"),
    ):
        oid = _id(item.get(key))
        if oid:
            return f"{kind}:{mid}{oid}" if mid else f"{kind}:{oid}"
    return None


def filter_items(me, items: list) -> list:
    if not me or not items:
        return items
    actors = hidden_actor_ids(me)
    stories = hidden_story_keys(me)
    out = []
    for it in items:
        actor = it.get("actor")
        aid = getattr(actor, "id", None)
        if aid and aid in actors and aid != me.id:
            continue
        sk = story_key_for(it)
        if sk and sk in stories:
            continue
        if sk:
            it["story_key"] = sk
        out.append(it)
    return out


def hide_actor(me, actor_id: int) -> bool:
    if not me or not actor_id or actor_id == me.id:
        return False
    FeedHide.objects.get_or_create(
        social_user=me, actor_id=actor_id,
        defaults={"created_at": now()},
    )
    bump_news()
    return True


def unhide_actor(me, actor_id: int) -> bool:
    if not me or not actor_id:
        return False
    n, _ = FeedHide.objects.filter(social_user=me, actor_id=actor_id).delete()
    if n:
        bump_news()
    return bool(n)


def hide_story(me, story_key: str) -> bool:
    key = (story_key or "").strip()[:80]
    if not me or not key or ":" not in key:
        return False
    FeedStoryHide.objects.get_or_create(
        social_user=me, story_key=key,
        defaults={"created_at": now()},
    )
    bump_news()
    return True


def hidden_people(me, limit=40):
    if not me:
        return []
    from apps.social.models import SocialProfile, profile_related
    ids = list(
        FeedHide.objects.filter(social_user=me).order_by("-id")
        .values_list("actor_id", flat=True)[:limit]
    )
    if not ids:
        return []
    by_id = {
        p.id: p
        for p in SocialProfile.objects.filter(id__in=ids).defer(*profile_related())
    }
    return [by_id[i] for i in ids if i in by_id]
