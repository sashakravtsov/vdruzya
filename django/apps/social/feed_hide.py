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
    kind = item.get("kind") or ""
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
