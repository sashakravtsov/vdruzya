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


def story_key_for(item: dict) -> str | None:
    """Stable per-story hide key. Kind-specific branches run before generic post/place/event."""
    kind = (item.get("kind") or "").strip()
    actor = item.get("actor")

    if kind == "hashtag":
        tag, post = item.get("tag"), item.get("post")
        if tag is not None and post is not None and getattr(tag, "id", None) and getattr(post, "id", None):
            return f"hashtag:{tag.id}:{post.id}"

    if kind == "safety":
        checkin = item.get("checkin")
        if checkin is not None and getattr(checkin, "id", None):
            return f"safety:{checkin.id}"

    if kind == "checkin":
        row = item.get("checkin")
        if row is not None and getattr(row, "id", None):
            return f"checkin:{row.id}"

    if kind == "review":
        row = item.get("review")
        if row is not None and getattr(row, "id", None):
            return f"review:{row.id}"

    if kind == "joined":
        group = item.get("group")
        if group is not None and actor is not None and getattr(group, "id", None) and getattr(actor, "id", None):
            return f"joined:{group.id}:{actor.id}"

    if kind == "created":
        group = item.get("group")
        if group is not None and actor is not None and getattr(group, "id", None) and getattr(actor, "id", None):
            return f"created:{group.id}:{actor.id}"

    if kind == "fan":
        page = item.get("page")
        if page is not None and actor is not None and getattr(page, "id", None) and getattr(actor, "id", None):
            return f"fan:{page.id}:{actor.id}"

    if kind == "market":
        listing = item.get("listing")
        if listing is not None and getattr(listing, "id", None):
            return f"market:{listing.id}"

    if kind == "anniversary" and actor is not None and getattr(actor, "id", None):
        years = item.get("years")
        return f"anniversary:{actor.id}:{years if years is not None else 0}"

    if kind == "group_doc":
        doc = item.get("doc")
        if doc is not None and getattr(doc, "id", None):
            return f"group_doc:{doc.id}"

    if kind in ("friend", "relationship"):
        other = item.get("other")
        if actor is not None and other is not None and getattr(actor, "id", None) and getattr(other, "id", None):
            a, b = sorted((actor.id, other.id))
            return f"{kind}:{a}:{b}"

    og = item.get("og")
    if og is not None and getattr(og, "id", None):
        return f"og:{og.id}"

    milestone = item.get("milestone")
    if milestone is not None and getattr(milestone, "id", None):
        prefix = "page_milestone" if kind == "page_milestone" else "milestone"
        return f"{prefix}:{milestone.id}"

    col = item.get("collection")
    if col is not None and getattr(col, "id", None):
        return f"collection:{col.id}"

    post = item.get("post")
    if post is not None and getattr(post, "id", None):
        return f"{kind}:{post.id}"

    photo = item.get("photo")
    if photo is not None and getattr(photo, "id", None):
        return f"{kind}:photo:{photo.id}"

    poll = item.get("poll")
    if poll is not None and getattr(poll, "id", None):
        return f"{kind}:poll:{poll.id}"

    question = item.get("question")
    if question is not None and getattr(question, "id", None):
        return f"{kind}:q:{question.id}"

    place = item.get("place")
    if place is not None and getattr(place, "id", None):
        return f"{kind}:place:{place.id}"

    event = item.get("event")
    if event is not None and getattr(event, "id", None):
        return f"{kind}:event:{event.id}"

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
        FeedHide.objects.filter(social_user=me).order_by("-id").values_list("actor_id", flat=True)[:limit]
    )
    if not ids:
        return []
    by_id = {
        p.id: p
        for p in SocialProfile.objects.filter(id__in=ids).defer(*profile_related())
    }
    return [by_id[i] for i in ids if i in by_id]
