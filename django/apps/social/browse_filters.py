"""Tiny News Feed / Friends browse filters (classic lists + kind tabs)."""
from __future__ import annotations

FEED_TABS = (
    ("all", "Все"),
    ("photos", "Фото"),
    ("links", "Ссылки"),
    ("videos", "Видео"),
    ("shares", "Репосты"),
    ("groups", "Группы"),
)
_FEED_KINDS = {
    "photos": frozenset({"photo", "photos", "photo_tag", "photo_like", "tagged", "picture"}),
    "links": frozenset({"link"}),
    "videos": frozenset({"video"}),
    "shares": frozenset({"share"}),
    "groups": frozenset({"group_post", "group_doc", "joined", "created"}),
}


def feed_filter(raw: str) -> str:
    f = (raw or "all").lower()
    return f if f == "all" or f in _FEED_KINDS else "all"


def apply_feed(items, filt: str, *, actor_ids=None, me=None):
    kinds = _FEED_KINDS.get(filt)
    if kinds:
        items = [i for i in items if i.get("kind") in kinds]
    if actor_ids is not None:
        allow = set(actor_ids)
        if me:
            allow.add(me.id)
        items = [i for i in items if getattr(i.get("actor"), "id", None) in allow]
    return items
