"""Stable News Feed hide keys — feed_hide.story_key_for re-exports."""
from __future__ import annotations


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


